# 06 - Route Overrides and Audit

These are extensions to the activity layer. Build them after `01` through `05`.

## Route-level overrides

Activity-level assignment is sometimes too coarse. Overrides add finer control and
leave the simple path as the default.

Precedence:

1. Explicit per-route assignment (one specific feature or step).
2. Activity-family assignment.
3. Tenant default provider and model.
4. Fixture provider, in local and test mode only.

Each route request carries:

- `route_id`, such as `summarize.document`, `review.line_edit`, `research.cited`
- `activity_id`
- required capabilities: `text`, `large_context`, `web_search`, `web_extract`,
  `image_generation`, `restricted_content`, and so on
- an optional minimum model family or version, where the product has a known quality
  floor
- an estimated cost tier and a label for the billing line

Example: a generation route uses the newest premium model, while a cleanup route uses a
cheaper model from the same provider. Both belong to related activities but have
separate routes.

Existing tenants keep their current behavior until they opt into overrides.

## Research with citations

A feature that must cite sources requires search and extraction capability.

- A provider with native search satisfies the route directly.
- A text-only provider satisfies it only when a separately configured search and
  extraction provider is present.
- Otherwise, fail closed with setup guidance. Do not run a weak research pass silently.

## Audit ledger

Extend the usage record with:

- `initiator_user_id`: who asked for the work
- `provider_account_owner_user_id`: whose key and budget paid for it
- `route_id`, `activity_id`, `provider_type`, `model`
- `source` and any fallback reason
- the access context at the time of the call

## Shared access

When user B works on a resource owned by user A, and the resource uses A's provider keys:

- The call is **charged to A's credential and budget**.
- The action is **attributed to B** as initiator.
- Both identities are recorded on every model call.

Acceptance test: a shared-access call uses the owner's credential, and the usage record
names both users.

## Acceptance criteria

- Existing tenants see no change until they opt in.
- A route can use a different model than the provider default.
- Unsupported research setups fail closed with actionable guidance.
- Shared-access model calls are auditable by initiator and credential owner.
- No credential appears in tool output, served payloads, or model-visible input.
