# Model Routing Design Package

A design package for **multi-provider model configuration** in an agentic app.
Users connect several model providers. Each product activity, such as summarizing,
writing, revising, classifying, or generating an image, is assigned a provider and
model. Every model call then resolves through that assignment, including calls
made from field-level AI assist controls.

The design is domain-neutral. It applies to any product that routes AI work to
several providers.

## Contents

| File | Purpose |
|---|---|
| `01-architecture.md` | Layers, resolution flow, principles |
| `02-activity-taxonomy-and-capabilities.md` | Activity IDs, capability gates, recommendation order, capability file |
| `03-tenant-config-and-secrets.md` | Per-tenant provider config, secret references, credential handling, quota behavior |
| `04-runtime-integration.md` | Call sites, constraints, gated activities, fallbacks, audit fields |
| `05-settings-ui-and-routing-diagram.md` | Settings panel, bezier routing diagram, field-level AI assist controls |
| `06-route-overrides-and-audit.md` | Per-route overrides, research policy, shared-access attribution |
| `07-lessons-and-pitfalls.md` | Known failure modes and the rules they produced |
| `08-implementation-plan.md` | Ordered build slices with acceptance criteria |
| `09-agent-profile-overrides.md` | Launch-time overrides per agent profile, applied at step 0 of the router |
| `reference/activity_router.py` | Reference router implementation |
| `reference/test_overrides.py` | Override and agent-profile tests (`python3 test_overrides.py`) |
| `reference/test_activity_router.py` | Precedence tests (runs without dependencies: `python3 test_activity_router.py`) |
| `reference/model-routing-panel.js` | Reference settings panel with the bezier routing diagram |
| `reference/model_capabilities.json` | Example capability file (replace with reviewed values) |

## How to use this with an agent

1. Give the agent this folder and describe the product it is building.
2. Read `01` through `04` first. They define the model.
3. Read `07` before writing code. It lists the expensive mistakes.
4. Build in the order of `08`. Each slice has an acceptance test.
5. Use `reference/` for exact shapes and working code. The numbered docs are the
   authoritative description.

## Caveats

- Model IDs, prices, and capabilities change quickly. Re-verify the capability file
  against each provider's current documentation before reuse.
- The reference code is self-contained and tested for routing logic. It is not wired
  to any live provider.
- No credentials belong in this package or in any routing file.

## License

MIT License. Copyright (c) 2026 Christopher C. Mitchell. See `LICENSE`.
