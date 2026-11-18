# 01 - Architecture

## Problem

One default provider for the whole product breaks down quickly:

- Different work needs different models. Planning and long-context analysis need
  strong reasoning and a large context window. Simple extraction needs a fast, cheap
  model. Image work needs an image-capable provider. Some content is refused or
  degraded by some providers, so it needs a provider whose policy allows it.
- Users should not need to know model IDs. They should see the task ("Document
  analysis", "Image editing") and choose a provider for it.
- Keys must never reach a model, a tool result, a log, or a served payload.

The design adds an **activity-routing layer** between product features and provider
execution:

```text
feature or control + activity + constraints
  -> tenant routing config          (which provider and model per activity)
  -> provider capability metadata   (what each provider can actually do)
  -> provider registry              (secret reference -> live or fixture provider)
  -> model call
```

## Layers

| Layer | Responsibility | Holds credentials? |
|---|---|---|
| Activity taxonomy | Stable activity IDs and plain-language labels | No |
| Capability metadata | Which providers can perform which activities; curated recommendations | No |
| Tenant routing store | Assignment of provider and model to each activity | No |
| Tenant provider config | Connected providers, preferred model, base URL | Encrypted key only, write-only |
| Secret resolver | Turns `secret://tenant/provider` into a key at call time | Yes, server-side only |
| Provider registry | Chooses a live or fixture provider | Through the resolver only |
| Activity router | Resolves (tenant, activity, constraints) to a provider and model | No |
| Settings UI and assist controls | Assignment, status, and per-field AI actions | Never |

The router carries **indirection only**. It returns a `secret://` reference, and the
registry resolves it later. Routing data can then be stored in ordinary files,
reviewed in diffs, and served by the API without exposing keys.

## Resolution order

For each activity the router tries these steps in order:

0. **Launch override.** An orchestrator can override the provider, model, or effort for one agent instance. The override must name a connected, capable provider, and it never changes the tenant's saved routing. See `09`.
1. **Explicit user assignment.** Must name a configured provider and must be capable
   of the activity.
2. **Curated recommendation.** The first configured provider that the capability
   file lists for this activity and that holds the required capability. This step
   deliberately **does not consult the default provider** (see `07`).
3. **Tenant default provider**, only if it holds the activity's required capability.
4. **Capability gate.** A gated activity that is still unserved raises an actionable
   error. This comes after the default check and before any platform fallback.
5. **Platform key**, for eligible tenants, only if the platform key holds the
   capability. Usage is metered and may carry a markup.

If nothing matches, raise a no-provider error with a reason the user can act on.

## Fail closed

When the right provider is not configured, pause and explain. Do not fall back to a
model that is likely to refuse, degrade, or fail with a raw error. Messages must
name the cause in user terms:

- No supported provider exists for this capability.
- A provider supports it but is not connected for this tenant.
- Connected providers support it but none is approved for this activity. A user key
  cannot fix this; it is a gap in the curated recommendations.

## Principles

1. Activity IDs are product-level. Providers map to activities, not the reverse.
2. The routing config never stores credentials.
3. A capability named for an activity must be sufficient. "The provider declares it"
   must mean "the provider can perform this" (see `02`).
4. Recommendations are advisory. Overwriting a user's explicit choice needs
   confirmation.
5. Constraints apply to the passage, item, or request that triggers them, not to a
   whole project.
6. Offline and test runs use a fixture provider and make no network calls.
7. The capability file lives in the repo and is reviewed like code, because it changes.
