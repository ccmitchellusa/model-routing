// Model-routing settings panel: reference implementation (generic).
//
// Maps each activity to one of the user's configured providers.
// Data in:  panel.data = { capabilities, routing }
//   capabilities: { providers: { <type>: { label } } }
//   routing: { activities: [{ activity_id, label, required, capable_providers,
//              recommended_providers, assignment: { provider_type, model, reasoning_effort } }],
//              missing_required: [activity_id], models_by_provider: { <type>: [model] },
//              reasoning_effort_options: [{ value, label }] }
// Events out (bubbling, composed):
//   'save-routing'           detail: { assignments }
//   'apply-routing-defaults' detail: {}
// The component never holds a credential.

const SVG_NS = 'http://www.w3.org/2000/svg';
const PALETTE = ['#2d83a8', '#cc785c', '#10a37f', '#4285f4', '#8e6fbf', '#c0392b'];

function safeText(value) {
  return typeof value === 'string' ? value : '';
}

function badgeColor(providerType) {
  let hash = 0;
  for (const ch of String(providerType)) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETTE[hash % PALETTE.length];
}

export class ModelRoutingPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.routing = null;
    this.capabilities = null;
    this._mode = 'preview'; // 'preview' (diagram) | 'edit' (form)
  }

  connectedCallback() {
    this.render();
  }

  set data(value) {
    if (value && value.routing && typeof value.routing === 'object') this.routing = value.routing;
    if (value && value.capabilities && typeof value.capabilities === 'object') {
      this.capabilities = value.capabilities;
    }
    this.render();
  }

  providerLabel(providerType) {
    const providers = this.capabilities && this.capabilities.providers;
    if (providers && providers[providerType] && providers[providerType].label) {
      return providers[providerType].label;
    }
    return providerType;
  }

  emit(name, detail) {
    this.dispatchEvent(new CustomEvent(name, { bubbles: true, composed: true, detail }));
  }

  saveRouting() {
    const assignments = {};
    for (const row of this.shadowRoot.querySelectorAll('.activity')) {
      const provider = row.querySelector('select.provider').value;
      if (!provider) continue; // unset means use the recommendation
      assignments[row.dataset.activity] = {
        provider_type: provider,
        model: (row.querySelector('input.model').value || '').trim(),
        reasoning_effort: (row.querySelector('select.reasoning').value || '').trim(),
      };
    }
    this.emit('save-routing', { assignments });
  }

  render() {
    const panel = document.createElement('section');
    panel.className = 'panel';
    panel.setAttribute('aria-label', 'Model routing');

    const head = document.createElement('div');
    head.className = 'head-row';
    const titles = document.createElement('div');
    const heading = document.createElement('h3');
    heading.textContent = 'Which model runs each task';
    const lead = document.createElement('p');
    lead.className = 'lead';
    lead.textContent =
      'Assign your connected providers to the work each does best. Leave a task unset to use the recommended provider.';
    titles.append(heading, lead);
    head.append(titles);
    if (this.routing) head.append(this.modeToggle());
    panel.append(head);

    if (!this.routing) {
      const empty = document.createElement('p');
      empty.className = 'empty';
      empty.textContent = 'Connect a provider to configure model routing.';
      panel.append(empty);
      this.shadowRoot.replaceChildren(this.styles(), panel);
      return;
    }

    const missing = this.routing.missing_required || [];
    if (missing.length) {
      const labels = {};
      for (const a of this.routing.activities || []) labels[a.activity_id] = a.label;
      const callout = document.createElement('p');
      callout.className = 'callout';
      callout.setAttribute('role', 'note');
      callout.textContent = `Needs a capable provider: ${missing
        .map((id) => labels[id] || id)
        .join(', ')}.`;
      panel.append(callout);
    }

    if (this._mode === 'edit') {
      const list = document.createElement('div');
      list.className = 'activities';
      for (const activity of this.routing.activities || []) list.append(this.renderActivity(activity));
      panel.append(list);

      const actions = document.createElement('div');
      actions.className = 'actions';
      const apply = document.createElement('button');
      apply.type = 'button';
      apply.className = 'mr-btn';
      apply.textContent = 'Use recommended for my default provider';
      apply.addEventListener('click', () => this.emit('apply-routing-defaults', {}));
      const save = document.createElement('button');
      save.type = 'button';
      save.className = 'mr-btn mr-btn--primary';
      save.textContent = 'Save routing';
      save.addEventListener('click', () => this.saveRouting());
      actions.append(apply, save);
      panel.append(actions);
    } else {
      panel.append(this.renderDiagram());
    }

    this.shadowRoot.replaceChildren(this.styles(), panel);
  }

  modeToggle() {
    const group = document.createElement('div');
    group.className = 'mode-toggle';
    group.setAttribute('role', 'tablist');
    for (const mode of ['preview', 'edit']) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'mr-toggle';
      btn.textContent = mode === 'preview' ? 'Preview' : 'Edit';
      btn.setAttribute('aria-selected', this._mode === mode ? 'true' : 'false');
      btn.addEventListener('click', () => {
        this._mode = mode;
        this.render();
      });
      group.append(btn);
    }
    return group;
  }

  // One row per activity: its effective provider and model, for the diagram.
  resolvedActivities() {
    return (this.routing.activities || []).map((a) => {
      const assigned = a.assignment && a.assignment.provider_type;
      return {
        id: a.activity_id,
        label: safeText(a.label),
        provider: assigned || (a.recommended_providers || [])[0] || '',
        model: (a.assignment && a.assignment.model) || '',
        isDefault: !assigned,
      };
    });
  }

  // Preview: activity pills on the left, provider nodes on the right, joined
  // by one cubic bezier per activity. Geometry matches docs/05.
  renderDiagram() {
    const wrap = document.createElement('div');
    wrap.className = 'diagram';
    const acts = this.resolvedActivities();
    const providers = [...new Set(acts.map((a) => a.provider).filter(Boolean))];
    if (!providers.length) {
      const empty = document.createElement('p');
      empty.className = 'empty';
      empty.textContent = 'No providers assigned yet. Switch to Edit to route each task.';
      wrap.append(empty);
      return wrap;
    }

    const W = 680;
    const rowH = 54;
    const H = Math.max(acts.length, providers.length) * rowH + 16;
    const x1 = 238; // right edge of the activity column
    const x2 = 410; // left edge of the provider column
    const yA = (i) => (H / (acts.length + 1)) * (i + 1);
    const yP = (j) => (H / (providers.length + 1)) * (j + 1);
    const providerIndex = {};
    providers.forEach((p, j) => {
      providerIndex[p] = j;
    });

    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.setAttribute('width', '100%');
    svg.setAttribute('class', 'route-svg');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'How each activity routes to a provider');

    // Routes first, so nodes sit on top of them.
    acts.forEach((a, i) => {
      if (!a.provider) return;
      const y1 = yA(i);
      const y2 = yP(providerIndex[a.provider]);
      const mid = (x1 + x2) / 2;
      const path = document.createElementNS(SVG_NS, 'path');
      path.setAttribute('d', `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`);
      path.setAttribute('class', a.isDefault ? 'route route-default' : 'route');
      svg.append(path);
    });

    acts.forEach((a, i) => {
      const fo = document.createElementNS(SVG_NS, 'foreignObject');
      fo.setAttribute('x', '6');
      fo.setAttribute('y', String(yA(i) - 17));
      fo.setAttribute('width', '232');
      fo.setAttribute('height', '34');
      const pill = document.createElement('div');
      pill.className = 'act-pill';
      const name = document.createElement('span');
      name.textContent = a.label;
      pill.append(name);
      if (a.isDefault) {
        const tag = document.createElement('span');
        tag.className = 'def-tag';
        tag.textContent = 'default';
        pill.append(tag);
      }
      fo.append(pill);
      svg.append(fo);
    });

    providers.forEach((p, j) => {
      const fo = document.createElementNS(SVG_NS, 'foreignObject');
      fo.setAttribute('x', String(x2));
      fo.setAttribute('y', String(yP(j) - 24));
      fo.setAttribute('width', '264');
      fo.setAttribute('height', '48');
      const node = document.createElement('div');
      node.className = 'prov-node';
      const badge = document.createElement('span');
      badge.className = 'brand-badge';
      badge.style.background = badgeColor(p);
      badge.textContent = this.providerLabel(p).charAt(0).toUpperCase();
      const info = document.createElement('div');
      info.className = 'prov-info';
      const name = document.createElement('div');
      name.className = 'prov-name';
      name.textContent = this.providerLabel(p);
      const models = [...new Set(acts.filter((a) => a.provider === p && a.model).map((a) => a.model))];
      const detail = document.createElement('div');
      detail.className = 'prov-models';
      detail.textContent = models.length ? models.join(', ') : 'recommended model';
      info.append(name, detail);
      node.append(badge, info);
      fo.append(node);
      svg.append(fo);
    });

    wrap.append(svg);
    return wrap;
  }

  renderActivity(activity) {
    const row = document.createElement('div');
    row.className = 'activity';
    row.dataset.activity = activity.activity_id;

    const head = document.createElement('div');
    head.className = 'activity-head';
    const label = document.createElement('span');
    label.className = 'activity-label';
    label.textContent = safeText(activity.label);
    head.append(label);
    if (activity.required) {
      const badge = document.createElement('span');
      badge.className = 'badge';
      badge.textContent = 'Needs capable provider';
      head.append(badge);
    }

    const controls = document.createElement('div');
    controls.className = 'activity-controls';

    const select = document.createElement('select');
    select.className = 'provider';
    select.setAttribute('aria-label', `Provider for ${activity.label}`);
    const unset = document.createElement('option');
    unset.value = '';
    unset.textContent = 'Recommended / unset';
    select.append(unset);
    const options = activity.capable_providers || [];
    for (const providerType of options) {
      const opt = document.createElement('option');
      opt.value = providerType;
      opt.textContent = this.providerLabel(providerType);
      select.append(opt);
    }
    const assigned = activity.assignment && activity.assignment.provider_type;
    if (assigned && options.includes(assigned)) select.value = assigned;

    // Datalist gives a dropdown of discovered models plus free text.
    const model = document.createElement('input');
    model.className = 'model';
    model.type = 'text';
    model.placeholder = 'Model: pick from the list or type';
    model.value = (activity.assignment && activity.assignment.model) || '';
    model.setAttribute('aria-label', `Model for ${activity.label}`);
    const listId = `mr-models-${activity.activity_id}`;
    const datalist = document.createElement('datalist');
    datalist.id = listId;
    model.setAttribute('list', listId);
    const fillModels = (providerType) => {
      datalist.replaceChildren();
      const byProvider = (this.routing && this.routing.models_by_provider) || {};
      for (const m of byProvider[providerType] || []) {
        const opt = document.createElement('option');
        opt.value = m;
        datalist.append(opt);
      }
    };
    fillModels(select.value);
    select.addEventListener('change', () => fillModels(select.value));

    const reasoning = document.createElement('select');
    reasoning.className = 'reasoning';
    reasoning.title = 'Applies to reasoning-capable models; ignored by others';
    reasoning.setAttribute('aria-label', `Reasoning level for ${activity.label}`);
    const effortOptions = (this.routing && this.routing.reasoning_effort_options) || [
      { value: '', label: 'Default' },
    ];
    for (const eo of effortOptions) {
      const opt = document.createElement('option');
      opt.value = eo.value;
      opt.textContent = `Reasoning: ${eo.label}`;
      reasoning.append(opt);
    }
    reasoning.value = (activity.assignment && activity.assignment.reasoning_effort) || '';

    controls.append(select, model, datalist, reasoning);

    if ((activity.recommended_providers || []).length) {
      const rec = document.createElement('span');
      rec.className = 'recommended';
      rec.textContent = `Recommended: ${activity.recommended_providers
        .map((p) => this.providerLabel(p))
        .join(', ')}`;
      controls.append(rec);
    }

    row.append(head, controls);
    return row;
  }

  styles() {
    const style = document.createElement('style');
    style.textContent = `
      :host { display: block; box-sizing: border-box; --mr-border: #d7dde0; --mr-muted: #5b6b70;
        --mr-surface: #ffffff; --mr-text: #1b2326; --mr-accent: #2d83a8; --mr-ring: #2d83a8; }
      @media (prefers-color-scheme: dark) {
        :host(:not([data-theme="light"])) { --mr-border: #3a464b; --mr-muted: #9aa7ad;
          --mr-surface: #14191b; --mr-text: #e8eef0; }
      }
      :host([data-theme="dark"]) { --mr-border: #3a464b; --mr-muted: #9aa7ad;
        --mr-surface: #14191b; --mr-text: #e8eef0; }
      button:focus-visible, select:focus-visible, input:focus-visible {
        outline: none; box-shadow: 0 0 0 3px var(--mr-ring); }
      .panel { display: grid; gap: 0.6rem; color: var(--mr-text); }
      .head-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
      h3 { margin: 0; font-size: 1.1rem; }
      .lead { margin: 0; color: var(--mr-muted); font-size: 0.92rem; }
      .empty { color: var(--mr-muted); }
      .callout { margin: 0.25rem 0; padding: 0.6rem 0.8rem; border-radius: 0.5rem;
        border: 1px solid var(--mr-border); font-size: 0.9rem; }
      .activities { display: grid; gap: 0.5rem; }
      .activity { display: grid; gap: 0.4rem; padding: 0.7rem 0.85rem; border: 1px solid var(--mr-border);
        border-radius: 10px; background: var(--mr-surface); }
      .activity-head { display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
      .activity-label { font-weight: 700; }
      .badge { font-size: 0.66rem; font-weight: 700; text-transform: uppercase; padding: 0.1rem 0.4rem;
        border-radius: 999px; color: var(--mr-muted); border: 1px solid var(--mr-border); }
      .activity-controls { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
      select.provider, input.model, select.reasoning {
        min-height: 40px; border: 1px solid var(--mr-border); border-radius: 8px;
        background: var(--mr-surface); color: var(--mr-text); font: inherit; padding: 0 0.5rem; }
      input.model { flex: 1 1 220px; min-width: 0; }
      .recommended { color: var(--mr-muted); font-size: 0.82rem; flex-basis: 100%; }
      .actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
      .mr-btn, .mr-toggle { font: inherit; font-size: 0.85rem; padding: 6px 14px; border-radius: 999px;
        border: 1px solid var(--mr-border); background: var(--mr-surface); color: var(--mr-text); cursor: pointer;
        transition: border-color 120ms ease, transform 120ms ease; }
      .mr-btn:hover { border-color: var(--mr-ring); }
      .mr-btn:active { transform: translateY(1px); }
      .mr-btn--primary { border-color: var(--mr-accent); }
      .mode-toggle { display: inline-flex; border: 1px solid var(--mr-border); border-radius: 999px; overflow: hidden; flex: none; }
      .mode-toggle .mr-toggle { border: 0; border-radius: 0; }
      .mode-toggle [aria-selected="true"] { background: var(--mr-accent); color: #fff; }
      .diagram { margin-top: 0.5rem; }
      .route-svg { display: block; max-width: 100%; overflow: visible; }
      .route { fill: none; stroke: var(--mr-accent); stroke-width: 1.6; opacity: 0.55; }
      .route-default { stroke: var(--mr-muted); stroke-dasharray: 4 4; opacity: 0.5; }
      .act-pill { display: flex; align-items: center; justify-content: space-between; gap: 6px; height: 34px;
        box-sizing: border-box; padding: 0 10px; border: 1px solid var(--mr-border); border-radius: 999px;
        background: var(--mr-surface); font-size: 0.82rem; font-weight: 600; overflow: hidden; }
      .act-pill > span:first-child { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .def-tag { flex: none; font-size: 0.58rem; text-transform: uppercase; color: var(--mr-muted);
        border: 1px solid var(--mr-border); border-radius: 999px; padding: 0 5px; }
      .prov-node { display: flex; align-items: center; gap: 8px; height: 48px; box-sizing: border-box;
        padding: 0 10px; border: 1px solid var(--mr-border); border-radius: 10px; background: var(--mr-surface); }
      .brand-badge { flex: none; width: 28px; height: 28px; border-radius: 7px; color: #fff;
        display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.92rem; }
      .prov-info { min-width: 0; }
      .prov-name { font-weight: 700; font-size: 0.86rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .prov-models { font-size: 0.74rem; color: var(--mr-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    `;
    return style;
  }
}

if (!customElements.get('model-routing-panel')) {
  customElements.define('model-routing-panel', ModelRoutingPanel);
}
