# 08 - Implementation Plan

Build in this order. Each slice has an acceptance test. Do not start a slice until the
previous one passes.

## Slice 1: Metadata foundation

- Activity taxonomy as constants, with labels and the required capability per activity.
- Capability vocabulary, with user-facing names.
- Capability file and a loader that validates the schema.

**Acceptance.** The loader rejects an unknown activity or capability. Every activity has
a label. Every recommended provider holds the capability its activities require.

## Slice 2: Tenant provider config and secrets

- Filesystem store for provider entries, with keys encrypted at rest.
- `SecretResolver` protocol and a local implementation.
- Read endpoint that returns `key_present`, never the key.
- Base URL validation at write time.

**Acceptance.** A read never returns a key. A metadata-range base URL is rejected. A key
round-trips through encryption.

## Slice 3: Routing store and resolver

- Routing store with assignments, validated against connected providers.
- `resolve` with the precedence in `01`.
- Typed errors: unknown activity, no provider, required assignment missing.

**Acceptance.** One test per precedence step. A gated activity without a capable provider
raises the gated error, not a generic one. Changing the default does not move a
recommended lane. The reference tests in `reference/` pass.

## Slice 4: Provider registry and fixture mode

- Registry that resolves a secret reference to a live or fixture provider.
- Fixture mode as the default in CI.

**Acceptance.** The full routing suite runs with no network access.

## Slice 5: Settings panel

- Preview (bezier diagram) and Edit modes, as in `05`.
- Save and "use recommended" actions that emit events to the host.
- Callout for unserved gated activities.

**Acceptance.** Render test: construct the component with sample data, and check the
diagram has one path per routed activity whose `d` attribute matches the formula in `05`.

## Slice 6: Provider setup flow

- Guided setup: choose provider, read instructions, enter the key in the settings panel,
  discover models, pick a model.
- Saving a provider as default offers recommended assignments and requires confirmation
  before overwriting.

**Acceptance.** Saving a key never returns it. Discovery uses the saved key on the server.

## Slice 7: Route preview and assist controls

- `GET /api/route-preview` as specified in `05`.
- Assist control component that shows its route, disables itself when gated, and calls
  the feature endpoint with an activity ID.
- Per-control override that saves an explicit assignment after confirmation.

**Acceptance.** A gated control with no capable provider is disabled and shows a setup
prompt, with no model call. A control with a route shows provider, model, and source
before any click.

## Slice 8: Runtime audit

- Find every model call that reads the default provider directly and convert it to an
  activity call.
- Add a test per feature asserting it resolves through the router.
- Record the audit fields in `04`.

**Acceptance.** A search for direct default-provider lookups in model-calling code finds
none. Every call's usage record has an activity ID and a source.

## Slice 9: Constraints

- Sensitivity or content constraints change the activity before resolution.
- A constraint applies only to the item that carries it.

**Acceptance.** A constrained item routes to the gated activity. The next unconstrained
item in the same project routes normally.

## Slice 10: Quota and resumable jobs

- Typed quota error mapped from provider signals.
- Job state that pauses instead of failing.
- Resume endpoint.

**Acceptance.** A simulated quota error moves the job to the paused state, and resume
re-runs it.

## Slice 11: Overrides and shared-access audit (optional)

- Per-route overrides and the audit fields in `06`.
- Shared-access attribution.

**Acceptance.** A shared-access call charges the owner's credential and records both users.

## Definition of done

- A tenant can connect more than one provider.
- A tenant can assign different providers and models to different activities.
- Making a provider the default assigns it only to activities it can reliably perform, and
  never overwrites user choices without confirmation.
- A gated activity is never served by a model that cannot perform it.
- Missing assignments produce a setup prompt, not a raw model error.
- Every assist control shows its route before the user invokes it.
- No credential appears in any API response, tool output, log, or model-visible input.
