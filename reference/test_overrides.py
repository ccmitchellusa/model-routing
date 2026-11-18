"""Launch-time override tests for the reference router.
Run: python3 test_overrides.py
"""

import sys
from pathlib import Path

from activity_router import (
    ActivityRouter,
    Assignment,
    InMemoryConfigStore,
    OverrideRejectedError,
    ProviderEntry,
    RequiredAssignmentMissingError,
    TenantConfig,
    load_capabilities,
)

CAPS = load_capabilities(Path(__file__).with_name("model_capabilities.json"))
TENANT = "tenant-a"


def router_with(*providers, default=None, assignments=None):
    store = InMemoryConfigStore()
    store.put(
        TENANT,
        TenantConfig(
            providers={p: ProviderEntry(p, preferred_model=f"{p}-default") for p in providers},
            default_provider=default,
            assignments=assignments or {},
        ),
    )
    return ActivityRouter(store, CAPS)


def raises(exc, fn):
    try:
        fn()
    except exc:
        return
    raise AssertionError(f"expected {exc.__name__}")


def test_override_beats_user_assignment_for_that_launch():
    r = router_with(
        "openai",
        "anthropic",
        assignments={"plan_project": Assignment("openai", model="gpt-x")},
    )
    res = r.resolve(
        TENANT,
        "plan_project",
        overrides={"plan_project": Assignment("anthropic", model="claude-x", reasoning_effort="high")},
    )
    assert (res.provider_type, res.model, res.reasoning_effort, res.source) == (
        "anthropic", "claude-x", "high", "override",
    )


def test_no_override_leaves_tenant_routing_unchanged():
    r = router_with("openai", "anthropic", assignments={"plan_project": Assignment("openai")})
    assert r.resolve(TENANT, "plan_project").source == "user"
    assert r.resolve(TENANT, "plan_project", overrides={}).source == "user"


def test_override_is_scoped_to_its_activity():
    r = router_with("openai", "anthropic")
    res = r.resolve(
        TENANT, "simple_task", overrides={"plan_project": Assignment("anthropic")}
    )
    assert res.source != "override"


def test_override_cannot_name_unconnected_provider():
    r = router_with("openai")
    raises(
        OverrideRejectedError,
        lambda: r.resolve(TENANT, "plan_project", overrides={"plan_project": Assignment("anthropic")}),
    )


def test_override_cannot_name_incapable_provider():
    # restricted_host is connected, but cannot perform image editing.
    r = router_with("openai", "restricted_host")
    raises(
        OverrideRejectedError,
        lambda: r.resolve(TENANT, "image_edit", overrides={"image_edit": Assignment("restricted_host")}),
    )


def test_override_does_not_bypass_gate_when_unset():
    # An override for another activity must not satisfy a gated activity.
    r = router_with("openai")
    raises(
        RequiredAssignmentMissingError,
        lambda: r.resolve(
            TENANT,
            "restricted_content_generation",
            overrides={"plan_project": Assignment("openai")},
        ),
    )


def test_override_keyed_by_effective_activity():
    # A restricted constraint turns long_form_generation into the restricted activity,
    # so the override must be keyed by that effective activity.
    from activity_router import Constraints

    r = router_with("restricted_host", "anthropic")
    res = r.resolve(
        TENANT,
        "long_form_generation",
        constraints=Constraints(sensitivity="restricted"),
        overrides={"restricted_content_generation": Assignment("restricted_host", reasoning_effort="low")},
    )
    assert (res.activity_id, res.provider_type, res.reasoning_effort, res.source) == (
        "restricted_content_generation", "restricted_host", "low", "override",
    )


def test_override_secret_ref_is_still_tenant_scoped():
    r = router_with("openai")
    res = r.resolve(TENANT, "plan_project", overrides={"plan_project": Assignment("openai")})
    assert res.secret_ref == f"secret://{TENANT}/openai"


def test_profile_overrides_apply_only_to_that_agent():
    from activity_router import AgentProfile

    r = router_with("openai", "anthropic")
    drafter = AgentProfile("drafter", overrides={"plan_project": Assignment("openai", model="gpt-x")})
    reviewer = AgentProfile("reviewer")
    assert r.resolve_for_agent(TENANT, drafter, "plan_project").provider_type == "openai"
    # The reviewer, and the tenant's own routing, still see the recommendation.
    assert r.resolve_for_agent(TENANT, reviewer, "plan_project").source == "recommendation"
    assert r.resolve(TENANT, "plan_project").source == "recommendation"


if __name__ == "__main__":
    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except Exception as e:  # noqa: BLE001
                failures += 1
                print("FAIL", name, e)
    sys.exit(1 if failures else 0)
