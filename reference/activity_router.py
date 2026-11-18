"""Activity-based model routing: reference implementation.

Pure routing logic plus an in-memory store. This module holds no credentials.
It returns ``secret://<tenant>/<provider>`` references, and a separate resolver
turns those into keys at call time.

Resolution order (see docs/01-architecture.md):
  1. explicit user assignment (must be configured and capable)
  2. curated recommendation among configured, capable providers
  3. tenant default provider, only if it is capable of the activity
  4. capability gate: a gated activity that is still unserved raises
  5. platform-key fallback, for eligible tenants, never for gated activities
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

BASELINE_CAPABILITY = "text"


# --- Activity taxonomy -----------------------------------------------------
# Stable IDs used in code, storage and the API. Labels are what users see.
# Replace these with the activities of your own product.


@dataclass(frozen=True)
class ActivitySpec:
    label: str
    required_capability: str = BASELINE_CAPABILITY
    # Gated activities must be served by a provider that holds the capability.
    # They never fall through to the platform key.
    gated: bool = False
    # Preferred providers, earlier entries first. Used only as a sort key over
    # providers that already curate the activity.
    recommended_order: tuple[str, ...] = ()


ACTIVITIES: dict[str, ActivitySpec] = {
    "brainstorm_ideas": ActivitySpec("Brainstorming ideas and options"),
    "plan_project": ActivitySpec(
        "Project planning and consistency",
        "large_context",
        recommended_order=("anthropic", "openai"),
    ),
    "long_form_generation": ActivitySpec("General long-form writing", "large_context"),
    "restricted_content_generation": ActivitySpec(
        "Restricted-content tasks", "restricted_content", gated=True
    ),
    "inline_assist": ActivitySpec("Inline assistant"),
    "precise_revision": ActivitySpec(
        "Precise text revision", recommended_order=("openai", "anthropic")
    ),
    "structure_review": ActivitySpec(
        "Structural review", "large_context", recommended_order=("anthropic", "openai")
    ),
    "mechanics_check": ActivitySpec(
        "Mechanical checks", recommended_order=("openai", "anthropic")
    ),
    "simple_task": ActivitySpec("Simple background tasks"),
    "document_extraction": ActivitySpec("Document analysis", "large_context"),
    "image_prompt": ActivitySpec("Image brief and art direction"),
    "image_generation": ActivitySpec(
        "Image creation", "image_generation", recommended_order=("openai",)
    ),
    # Editing is narrower than generation. Only a provider with a real edit
    # endpoint may hold this capability.
    "image_edit": ActivitySpec(
        "Image editing", "image_edit", gated=True, recommended_order=("openai",)
    ),
    "output_formatting": ActivitySpec("Output formatting and checks"),
}

# Content constraint: a passage marked "restricted" routes to the restricted
# activity. Only that passage is affected, not the whole project.
RESTRICTED = "restricted"


# --- Errors ----------------------------------------------------------------


class ModelRoutingError(ValueError):
    """Base class for routing configuration and resolution failures."""


class UnknownActivityError(ModelRoutingError):
    pass


class NoProviderConfiguredError(ModelRoutingError):
    pass


class RequiredAssignmentMissingError(ModelRoutingError):
    """A gated activity has no capable, approved provider. The message is
    written for the user, so the UI can show a setup prompt."""


# --- Data ------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderCapability:
    provider_type: str
    label: str
    capabilities: frozenset[str]
    recommended: frozenset[str] = frozenset()

    def can_perform(self, activity_id: str) -> bool:
        return ACTIVITIES[activity_id].required_capability in self.capabilities


@dataclass(frozen=True)
class ProviderEntry:
    provider_type: str
    preferred_model: str = ""


@dataclass(frozen=True)
class Assignment:
    provider_type: str
    model: str = ""
    reasoning_effort: str = ""  # "" means the model default


@dataclass
class TenantConfig:
    providers: dict[str, ProviderEntry] = field(default_factory=dict)
    default_provider: str | None = None
    assignments: dict[str, Assignment] = field(default_factory=dict)


@dataclass(frozen=True)
class Constraints:
    sensitivity: str | None = None


@dataclass(frozen=True)
class ResolvedModel:
    activity_id: str
    provider_type: str
    model: str
    secret_ref: str
    source: str  # "user" | "recommendation" | "fallback" | "platform"
    reasoning_effort: str = ""
    managed: bool = False  # True when the platform key was used


class TenantConfigStore(Protocol):
    def get(self, tenant_id: str) -> TenantConfig: ...


class PlatformFallback(Protocol):
    """Optional platform-key policy for eligible tenants."""

    def eligible(self, tenant_id: str) -> bool: ...
    def capable(self, activity_id: str) -> bool: ...


class InMemoryConfigStore:
    """Test and demo store. A real store persists per tenant."""

    def __init__(self) -> None:
        self._configs: dict[str, TenantConfig] = {}

    def get(self, tenant_id: str) -> TenantConfig:
        return self._configs.setdefault(tenant_id, TenantConfig())

    def put(self, tenant_id: str, config: TenantConfig) -> None:
        self._configs[tenant_id] = config


def load_capabilities(path: str | Path) -> dict[str, ProviderCapability]:
    """Load the reviewable capability file (see reference/model_capabilities.json)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1:
        raise ModelRoutingError("unsupported capability schema_version")
    out: dict[str, ProviderCapability] = {}
    for provider_type, body in raw["providers"].items():
        unknown = set(body.get("recommended_activities", [])) - set(ACTIVITIES)
        if unknown:
            raise ModelRoutingError(f"{provider_type}: unknown activities {sorted(unknown)}")
        out[provider_type] = ProviderCapability(
            provider_type=provider_type,
            label=body.get("label", provider_type),
            capabilities=frozenset(body.get("capabilities", [])),
            recommended=frozenset(body.get("recommended_activities", [])),
        )
    return out


def secret_ref(tenant_id: str, provider_type: str) -> str:
    # Indirection only. The registry resolves this to a key on the server.
    return f"secret://{tenant_id}/{provider_type}"


# --- Router ----------------------------------------------------------------


class ActivityRouter:
    def __init__(
        self,
        configs: TenantConfigStore,
        capabilities: dict[str, ProviderCapability],
        platform: PlatformFallback | None = None,
        platform_tenant_id: str = "platform",
    ) -> None:
        self._configs = configs
        self._caps = capabilities
        self._platform = platform
        self._platform_tenant = platform_tenant_id

    # Constraints change which activity runs, before resolution.
    def effective_activity(self, activity_id: str, constraints: Constraints | None) -> str:
        if (
            activity_id == "long_form_generation"
            and constraints is not None
            and (constraints.sensitivity or "").lower() == RESTRICTED
        ):
            return "restricted_content_generation"
        return activity_id

    def recommended_providers(self, activity_id: str) -> list[str]:
        """Providers that curate this activity and can perform it, best first."""
        order = ACTIVITIES[activity_id].recommended_order
        candidates = [
            c.provider_type
            for c in self._caps.values()
            if activity_id in c.recommended and c.can_perform(activity_id)
        ]

        def rank(p: str) -> tuple[int, str]:
            return (order.index(p) if p in order else len(order), p)

        return sorted(candidates, key=rank)

    def missing_required(self, tenant_id: str) -> list[str]:
        """Gated activities this tenant cannot currently serve."""
        missing = []
        for activity_id, spec in ACTIVITIES.items():
            if not spec.gated:
                continue
            try:
                self.resolve(tenant_id, activity_id)
            except RequiredAssignmentMissingError:
                missing.append(activity_id)
            except ModelRoutingError:
                pass
        return missing

    def resolve(
        self,
        tenant_id: str,
        activity_id: str,
        *,
        constraints: Constraints | None = None,
    ) -> ResolvedModel:
        if activity_id not in ACTIVITIES:
            raise UnknownActivityError(f"unknown activity: {activity_id}")
        activity = self.effective_activity(activity_id, constraints)
        spec = ACTIVITIES[activity]
        cfg = self._configs.get(tenant_id)
        configured = cfg.providers

        def capable(provider_type: str) -> bool:
            cap = self._caps.get(provider_type)
            return cap is not None and cap.can_perform(activity)

        def model_for(provider_type: str, assigned_model: str) -> str:
            if assigned_model.strip():
                return assigned_model
            entry = configured.get(provider_type)
            return entry.preferred_model if entry else ""

        # 1) Explicit user assignment.
        assignment = cfg.assignments.get(activity)
        if assignment is not None and assignment.provider_type in configured:
            if not capable(assignment.provider_type):
                raise RequiredAssignmentMissingError(
                    self._unmet_message(activity, assignment.provider_type, configured)
                )
            return ResolvedModel(
                activity_id=activity,
                provider_type=assignment.provider_type,
                model=model_for(assignment.provider_type, assignment.model),
                secret_ref=secret_ref(tenant_id, assignment.provider_type),
                source="user",
                reasoning_effort=assignment.reasoning_effort,
            )

        # 2) Curated recommendation. Never consults the default provider, so
        #    changing the default does not move lanes that have a recommendation.
        for provider_type in self.recommended_providers(activity):
            if provider_type in configured:
                return ResolvedModel(
                    activity_id=activity,
                    provider_type=provider_type,
                    model=model_for(provider_type, ""),
                    secret_ref=secret_ref(tenant_id, provider_type),
                    source="recommendation",
                )

        # 3) Tenant default, only if it is capable of this activity.
        default = cfg.default_provider
        if default and default in configured and capable(default):
            return ResolvedModel(
                activity_id=activity,
                provider_type=default,
                model=model_for(default, ""),
                secret_ref=secret_ref(tenant_id, default),
                source="fallback",
            )

        # 4) Gate. Runs before the platform fallback, so a gated activity never
        #    lands on the platform key.
        if spec.gated:
            raise RequiredAssignmentMissingError(
                self._unmet_message(activity, None, configured)
            )

        # 5) Platform key for eligible tenants, if the platform key is capable.
        if self._platform is not None and self._platform.eligible(tenant_id):
            if self._platform.capable(activity):
                return ResolvedModel(
                    activity_id=activity,
                    provider_type="platform",
                    model="",
                    secret_ref=secret_ref(self._platform_tenant, "platform"),
                    source="platform",
                    managed=True,
                )

        if not configured:
            raise NoProviderConfiguredError("no model provider is configured")
        raise NoProviderConfiguredError(
            f"no configured provider can perform '{spec.label}'"
        )

    def _unmet_message(
        self, activity: str, assigned: str | None, configured: dict[str, ProviderEntry]
    ) -> str:
        spec = ACTIVITIES[activity]
        cap = spec.required_capability
        if assigned is not None:
            name = self._caps[assigned].label if assigned in self._caps else assigned
            return (
                f"'{spec.label}' is assigned to {name}, which cannot perform it. "
                f"Choose a provider that supports {cap}."
            )
        supporters = [p for p, c in self._caps.items() if cap in c.capabilities]
        if not supporters:
            return f"No supported provider can perform '{spec.label}'."
        if not any(p in configured for p in supporters):
            return f"'{spec.label}' needs a provider with {cap}. Connect one in Settings."
        return f"'{spec.label}' has no approved provider. Assign one in Settings."
