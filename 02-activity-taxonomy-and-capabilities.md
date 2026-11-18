# 02 - Activity Taxonomy and Capabilities

## Activity IDs

Activity IDs are stable strings used in code, storage, and the API. Labels are what
users see. Raw IDs should not appear in normal UI.

The reference taxonomy is in `reference/activity_router.py`. It is a template and
should be replaced with the activities of your product.

| Activity ID | User-facing label | Required capability | Gated |
|---|---|---|---|
| `brainstorm_ideas` | Brainstorming ideas and options | text | no |
| `plan_project` | Project planning and consistency | large_context | no |
| `long_form_generation` | General long-form writing | large_context | no |
| `restricted_content_generation` | Restricted-content tasks | restricted_content | yes |
| `inline_assist` | Inline assistant | text | no |
| `precise_revision` | Precise text revision | text | no |
| `structure_review` | Structural review | large_context | no |
| `mechanics_check` | Mechanical checks | text | no |
| `simple_task` | Simple background tasks | text | no |
| `document_extraction` | Document analysis | large_context | no |
| `image_prompt` | Image brief and art direction | text | no |
| `image_generation` | Image creation | image_generation | no |
| `image_edit` | Image editing | image_edit | yes |
| `output_formatting` | Output formatting and checks | text | no |

Rules for the taxonomy:

- Add an activity when a distinct feature needs its own model choice, its own usage
  record, or its own capability gate. Do not add one per screen.
- Split an activity when two uses need different models. Precision revision needs an
  instruction-following model that changes only what was asked. Long-form generation
  needs a model with a large context. They are separate activities.
- Field-level AI controls use the same IDs. See `05` for how they call the router.

## Capabilities

Each provider declares a set of capabilities. Reference examples:

- `text`: baseline for any text activity
- `reasoning`: multi-step reasoning
- `large_context`: long input
- `image_generation`: create images
- `image_edit`: change an existing image. A narrower guarantee than generation
- `restricted_content`: permitted for content that some providers refuse

Each activity names **at most one** required capability. Activities that name none
require only `text`.

### Sufficiency

A required capability must be **sufficient**, not merely *necessary*. Declaring it
must mean the provider can perform the activity.

A concrete failure from the source project: an image-editing activity required the
coarse `image_generation` capability. One provider held that capability but had no
image-editing endpoint. Routing accepted it, and the call failed later with a less
clear error. The fix was a narrower `image_edit` capability, held only by providers
with a real edit endpoint.

If an activity needs a narrower guarantee than an existing capability gives, add a
narrower capability. Do not reuse the near miss.

## Recommendation order

For activities with a known quality preference, list providers in order. The router
picks the first **configured** provider in that order. Examples:

- Instruction-following providers first for precise revision and structured output.
- Strongest reasoning and largest context first for planning and structure review.
- Cheap, fast providers first for simple background tasks.

Providers not listed for an activity order alphabetically after those that are. The
order is a sort key over providers that already curate the activity. It is not a
source of candidates.

## Capability file

Store this as a versioned JSON file in the repo, reviewed in diffs. The reference
copy is `reference/model_capabilities.json`:

```json
{
  "schema_version": 1,
  "last_reviewed_at": "YYYY-MM-DD",
  "providers": {
    "openai": {
      "label": "OpenAI",
      "capabilities": ["text", "reasoning", "large_context", "image_generation", "image_edit"],
      "recommended_activities": ["plan_project", "precise_revision", "image_edit"]
    }
  }
}
```

Field semantics:

- `recommended_activities`: activities this provider is curated for. This is a
  suggestion, not a permanent rule.
- `last_reviewed_at` and `source_urls` (optional): when and from where the entry was
  checked. Model landscapes change faster than code.
- `deprecated_models` and `model_patterns` (optional): for model discovery.

Advanced users should still be able to enter a custom model ID that is not in the
file.

## One source for two consumers

The router's capability check and the settings UI's assignable-provider list and
missing-requirement warning must read the same map. If they come from different
sources they will disagree, and the UI will offer providers the router then rejects.
