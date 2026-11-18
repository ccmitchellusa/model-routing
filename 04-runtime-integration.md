# 04 - Runtime Integration

## The rule

Model-calling code never reads a default provider directly. Every model call names an
activity and goes through the router. This applies to background jobs, API endpoints,
and field-level AI controls alike:

```python
resolved = router.resolve(tenant_id, "precise_revision", constraints=constraints)
provider = registry.get(resolved.secret_ref, model=resolved.model,
                        reasoning_effort=resolved.reasoning_effort)
```

`ResolvedModel` contains:

- `activity_id`
- `provider_type` and `model`
- `secret_ref`
- `source`: `user`, `recommendation`, `fallback`, or `platform`
- `reasoning_effort`: the model default, or an override
- `managed`: true when the platform key was used

## Call sites

Map each model-using feature to an activity. Example mapping:

| Feature | Activity |
|---|---|
| Inline assistant panel | `inline_assist` |
| Field-level "improve this text" control | `precise_revision` |
| Field-level "suggest options" control | `brainstorm_ideas` |
| Project planning run | `plan_project` |
| Long-form generation job | `long_form_generation`, or `restricted_content_generation` by constraint |
| Image brief helper | `image_prompt` |
| Image generation job | `image_generation` |
| Image editing job | `image_edit` |
| Document import and analysis | `document_extraction` |
| Review pass | `structure_review`, `mechanics_check` |

Audit the code for direct default-provider lookups. Convert each one, and add a test
per feature that asserts it resolves through the router.

## Constraints

Constraints can change which activity runs, without changing feature code:

```json
{
  "activity_id": "long_form_generation",
  "sensitivity": "restricted",
  "requires_large_context": true,
  "max_cost_tier": "standard"
}
```

The router applies constraints before resolving. For example, a restricted sensitivity
level on general generation becomes the restricted-content activity.

The constraint applies only to the passage, item, or request that carries it. Other
items in the same project keep their normal routing.

## Gated activities

A gated activity needs a provider that holds its capability. If none is connected and
approved:

- Raise a typed `RequiredAssignmentMissingError`.
- The feature pauses and shows a setup prompt, such as "This task needs a provider
  that supports restricted content. Connect one in Settings."
- The feature does **not** retry on a provider likely to refuse.

Gated activities never fall through to the platform key. Only non-gated activities may
use the platform fallback.

## Platform fallback

For eligible tenants with no capable provider of their own:

- Route to the platform key, but only if the platform key holds the activity's
  capability.
- Mark the resolution `managed: true`.
- Meter the spend and apply any markup.

This is the last step. It is a convenience and must never override a capability gate.

## Fixture mode

When live providers are off (CI, offline development, demos), the registry returns a
fixture provider. The router still runs and still returns a reference, so routing
logic is tested without network calls.

Test these:

- Precedence, with each step tested separately.
- A gated activity with and without a capable provider.
- A default that is and is not capable.
- An unknown activity ID.
- Platform fallback when eligible and when not.

## Audit fields

Every model call records:

- `initiator_user_id`: who triggered the call
- `tenant_id` and `scope_id` (project, workspace, or request scope)
- `provider_account_owner_user_id`: whose credentials paid for the call, when that
  differs from the initiator
- `provider_type` and `model`
- `activity_id` and the route or feature that asked for it
- `source` and any fallback reason

See `06` for shared-access cases.
