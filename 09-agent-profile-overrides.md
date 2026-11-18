# 09 - Agent Profile Overrides

## Problem

The tenant's routing config is the default for every agent serving that tenant. That is
usually right, but an orchestrator launching agents sometimes needs a different choice
for one agent: a cheaper model for a bulk task, a stronger reasoning level for a review,
or a specific provider for one profile. The override must apply to that agent instance
only and must not change the tenant's saved routing.

## Concepts

- **Agent profile**: a named role, such as `drafter` or `reviewer`. It carries the
  launch-time overrides for that role.
- **Override**: an activity ID mapped to an assignment (provider, model, reasoning effort),
  chosen by the orchestrator when it launches the agent.
- **Launch scope**: the override lives on the agent instance (or its run record). It is
  not written to the tenant config.

```text
AgentProfile(profile_id="reviewer",
             overrides={ "structure_review": Assignment("anthropic", model="...", reasoning_effort="high") })
```

## Resolution

Overrides are step 0 of the router. They come before every tenant setting:

0. **Launch override** for this agent instance.
1. Tenant explicit user assignment.
2. Curated recommendation.
3. Tenant default provider, if capable.
4. Capability gate.
5. Platform key, for eligible tenants.

Rules for step 0:

- The provider must be **connected** for this tenant. An override cannot add a provider.
- The provider must be **capable** of the activity. The capability check is not skipped.
- An override does **not** satisfy a gate for a different activity. A gated activity with
  no override still raises the gated error.
- The platform key is never reached through an override. The override names a connected
  provider, and the key is still resolved from the tenant's secret reference.
- Overrides are keyed by the **effective** activity, after constraints are applied. An
  override on `restricted_content_generation` applies when a passage routes there.

A rejected override raises a distinct error (`OverrideRejectedError`), so the orchestrator
can tell a bad launch request from a tenant configuration problem.

## Where the orchestrator sets it

The orchestrator builds the profile at launch time and passes it with the agent request:

```python
profile = AgentProfile(
    profile_id="reviewer",
    overrides={"structure_review": Assignment("anthropic", reasoning_effort="high")},
)
resolved = router.resolve_for_agent(tenant_id, profile, "structure_review")
```

The orchestrator should not be able to choose a credential, a secret reference, or a
tenant. It chooses only an activity, a connected provider, a model, and an effort level.

## Effect on the agent runtimes

Whatever the runtime, the resolved values replace the tenant defaults for that one call:

- **Local runtime** writes its per-dispatch config from the resolved provider, model, and
  effort. Nothing is shared with other agents, so the override cannot leak.
- **Bridge runtime** sends the resolved provider, model, and key on that request only.
- **Direct provider calls** use the resolved model. Effort handling depends on the
  provider, and should be documented per provider.

## Audit

Every call made under an override records:

- the `profile_id` and the orchestrator run or launch ID
- `source = "override"` and the activity ID
- the provider and model that were actually used

This lets an audit answer: "Which agent chose this model, and why?"

## Acceptance tests

Covered in `reference/test_overrides.py`:

- An override beats the tenant's saved assignment for that launch only.
- With no override, the tenant's routing applies unchanged.
- An override applies only to its own activity.
- An override naming an unconnected provider is rejected.
- An override naming an incapable provider is rejected.
- An override does not satisfy a gate for a different activity.
- Overrides are keyed by the effective activity under constraints.
- The secret reference stays tenant-scoped.
- Two profiles for the same tenant resolve independently.
