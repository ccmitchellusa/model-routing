# 05 - Settings UI, Routing Diagram, and Field-Level AI Controls

## Purpose

The settings panel answers one question in plain language: **which connected provider
runs each kind of task?** It must work for someone who has never seen a model ID.

Field-level AI controls, such as an assist button beside a text field, are the other
place users meet routing. They must show which route will serve them, without making
the user open Settings first.

## Settings panel: two modes

A segmented toggle switches between:

- **Preview** (default): a read-only routing diagram that shows where each activity
  goes.
- **Edit**: one row per activity, with a provider dropdown, a model field, and a
  reasoning-level selector.

Preview is the default because most visits are checks, not changes.

### Edit mode

For each activity:

- The plain-language label, with a "Needs capable provider" badge for gated activities.
- A provider select. The first option is **"Recommended / unset"**. The rest are only
  providers that are both connected and capable of the activity.
- A model input with a datalist. The list repopulates when the provider changes.
  Users pick a discovered model or type a custom ID.
- A reasoning-level select (Default, Low, Medium, High, Extra-high). It applies only to
  reasoning-capable models.
- A "Recommended: ..." line listing curated providers.

Actions:

- **Use recommended for my default provider**: applies recommendations, and asks for
  confirmation before overwriting user choices.
- **Save routing**: sends assignments to the server.

A callout appears only when a gated activity is unserved, and names the activities.

### Preview: the bezier routing diagram

This is the signature element. Each activity is drawn as a line into the provider it
routes to.

```text
[ activity pills ]  ----bezier routes---->  [ provider nodes + model names ]
   left column (x = 6..238)                     right column (x = 410..674)
```

- **Activity pills** on the left, with the label. Activities served by the default
  provider get a small "default" tag.
- **Provider nodes** on the right, with a badge, the provider name, and the models
  assigned to it.
- **Routes**: one cubic bezier per activity, from its pill to its provider.
- **Default routes** are dashed and muted. Explicit assignments are solid.

Geometry (matches `reference/model-routing-panel.js`):

```text
W    = 680                       viewBox width
rowH = 54                        vertical unit
H    = max(activities, providers) * rowH + 16
x1   = 238                       activity column right edge (route start)
x2   = 410                       provider column left edge (route end)
yA(i) = H / (activities + 1) * (i + 1)
yP(j) = H / (providers + 1) * (j + 1)
```

Each route is a single cubic bezier:

```text
M x1,y1  C mid,y1  mid,y2  x2,y2     where mid = (x1 + x2) / 2
```

Both control points share the midpoint x. The curve leaves the pill horizontally,
bends through the middle, and enters the node horizontally. With control points at the
same x, the curve has no corners and no overshoot.

Pills are placed at `yA(i) - 17` with height 34. Nodes are placed at `yP(j) - 24`
with height 48, so each route meets the centre of its two endpoints.

Why curves and not right-angle lines: when many activities share one provider, smooth
curves read as flows. The eye can follow each activity to its provider and see the
fan-in at a glance. The diagram is for understanding, not for editing paths.

Styling: routes use the accent colour at about 0.55 opacity and 1.6px stroke. Default
routes are dashed. Badges use a provider-specific colour and a short glyph, not a
trademarked logo. All colours come from CSS custom properties, so the diagram follows
the theme.

Empty states: with no provider connected, show "Connect a provider to configure model
routing" and no diagram. With providers but no assignments, suggest Edit mode.

## Field-level AI assist controls

An assist control is a small button or menu beside a text field, image slot, or
structured input. Examples: "Improve selected text", "Suggest options", "Write a prompt
for this image".

Each control declares its **activity ID**. It does not declare a provider.

```text
user clicks control
  -> control sends { activity_id, input, constraints } to the feature endpoint
  -> feature calls router.resolve(tenant, activity_id, constraints)
  -> control shows the resolved route, then the result or the setup prompt
```

### What the control shows

Before the user invokes the control, it shows the route it will use. This comes from
a preview endpoint that resolves the route without calling a model:

- Provider label and model, such as "Anthropic, model name" or "OpenAI, default model".
- Source: "Your choice", "Recommended", "Default provider", or "Platform key".
- A billing hint when the platform key is used.

The preview is cheap and safe to call on focus. It returns no key, no request payload,
and no cost estimate it cannot back up.

### States

| State | What the control does |
|---|---|
| Route resolved | Enabled. Label shows the route. Clicking runs the activity. |
| Gated and unserved | Disabled, with the reason and a "Connect a provider" link. No model call. |
| Quota exhausted | Shows that the request is queued and will resume, not an error. |
| Provider error | Shows a plain message and offers to retry or change the route. |

A gated control never silently sends work to a provider likely to refuse it.

### Per-control override

A control can offer "Use a different provider for this" when more than one provider is
capable. Choosing one asks whether to save it as the assignment for this activity, or
to use it once. Saving writes an explicit user assignment, which goes through the same
validation as the Settings panel.

### Example: assist button in a page

```js
// Reference only. Replace the fetch paths with your own API.
class AssistButton extends HTMLElement {
  connectedCallback() {
    this.activity = this.getAttribute('activity');   // e.g. "precise_revision"
    this.target = document.querySelector(this.getAttribute('target'));
    this.innerHTML = '<button type="button" class="mr-btn">Assist</button><span class="route"></span>';
    this.button = this.querySelector('button');
    this.routeLabel = this.querySelector('.route');
    this.button.addEventListener('click', () => this.run());
    this.showRoute();
  }

  async showRoute() {
    const res = await fetch(`/api/route-preview?activity=${encodeURIComponent(this.activity)}`,
                            { credentials: 'same-origin' });
    const r = await res.json();
    this.button.disabled = !r.ready;
    this.routeLabel.textContent = r.ready
      ? `${r.provider_label}${r.model ? ' - ' + r.model : ''} (${r.source_label})`
      : r.setup_message;
  }

  async run() {
    this.button.disabled = true;
    const res = await fetch('/api/assist', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ activity_id: this.activity, input: this.target.value }),
    });
    const out = await res.json();
    if (out.result) this.target.value = out.result;
    this.button.disabled = false;
    this.showRoute();
  }
}
customElements.define('assist-button', AssistButton);
```

The server side of this is a thin endpoint: validate the activity ID, call
`router.resolve`, call the provider through the registry, and record the audit fields
from `04`. The browser never sees a key.

### Preview endpoint

```text
GET /api/route-preview?activity=<activity_id>
  -> { ready, provider_label, model, source, source_label, setup_message }
```

Return `ready: false` with `setup_message` when the route cannot resolve. Never return
a key, a secret reference, or a stack trace.

## Accessibility

- Mode toggle: `role="tablist"` with `aria-selected`.
- Diagram: `role="img"` with a descriptive `aria-label`.
- Every select and input has an `aria-label` naming its activity.
- Assist buttons state their route in text, not only in colour.
- Visible focus rings on all controls.

## Plain language

Use labels such as "Project planning and consistency", "Precise text revision",
"Simple background tasks", "Image creation". Raw activity IDs stay out of normal UI.
Error messages name the activity by its label and the provider by its display name.
