# 07 - Lessons and Pitfalls

Each entry is a failure mode from an earlier implementation and the rule it produced.

## 1. A default must not decide curated lanes

**What happened.** The recommendation step consulted the default provider. Changing the
default silently moved every activity, including ones the user had routed on purpose.

**Rule.** The recommendation step ignores the default. The default is a fallback,
consulted only after recommendations are exhausted. Changing it moves only the lanes
that reach that fallback.

## 2. Capabilities must be sufficient

**What happened.** An image-editing activity required the coarse `image_generation`
capability. A provider held it but had no edit endpoint. Routing accepted it, and the
call failed later with an unclear error.

**Rule.** A capability named for an activity must mean the provider can perform it. When
the match is only close, add a narrower capability.

## 3. Gated activities must not fall through

**What happened.** An early version applied the capability gate before the default
fallback. That made any activity with no curated provider unroutable, even when the
default could serve it.

**Rule.** The order is: user, recommendation, default (if capable), gate, platform key.
The gate runs after the default check, so a capable default still serves the lane. The
gate runs before the platform key, so a gated activity never lands on the platform key.

## 4. Constraints apply to the item, not the project

**What happened.** The design first considered routing an entire project to a specialist
model because one item needed it.

**Rule.** A constraint applies only to the item or request that carries it. Other items in
the same project keep normal routing. This keeps restricted or expensive models out of
most calls.

## 5. Never pass credentials through agent tools

**What happened.** The design nearly allowed a provider-setup tool whose schema could carry
a key. Tool arguments and results are visible to the model.

**Rule.** Credentials enter only through the human settings channel and go straight to an
authenticated endpoint. No agent tool accepts a credential. Catalog validators reject
credential-named fields, and a test scans the catalogs.

## 6. Keep recommendations reviewable and dated

**What happened.** Model names and capabilities changed within months.

**Rule.** The capability file lives in the repo, with `last_reviewed_at` and source links.
Changes go through diffs. Advanced users can still enter a custom model ID.

## 7. Router and UI read the same map

**What happened.** The UI's list of assignable providers and the router's check drifted
apart, so the UI offered options the router rejected.

**Rule.** Both read the same capability map. The UI derives its warnings from it.

## 8. Name the cause of a gap in user terms

**What happened.** A generic "no provider" error gave users no next step.

**Rule.** Distinguish three cases: no provider supports the capability; a provider supports
it but is not connected; connected providers support it but none is approved for the
activity. Each has a different fix, and the message says which applies.

## 9. Treat base URLs as an attack surface

**What happened.** Local providers need a user-supplied base URL, which can point at
internal services.

**Rule.** Allow only web schemes. Always reject metadata and reserved addresses. Allow
loopback and private ranges only on self-hosted deployments. Enforce at the write endpoint
and again at use.

## 10. Test render code at runtime

**What happened.** Render methods that passed a syntax check threw errors only when run
inside the full component, because a helper was out of scope.

**Rule.** Construct the component with sample data and call its render. A syntax check
alone misses scope errors.

## 11. Reasoning effort belongs to the model

**What happened.** A reasoning control applied to models that do not support it had no
effect and confused users.

**Rule.** Offer the control per activity, label it as applying to reasoning models only,
and ignore it for other models.

## 12. Assist controls must show their route

**What happened.** Assist buttons called the default provider directly. Users could not
tell which model would answer, and gated controls failed with raw model errors.

**Rule.** Every assist control resolves its route through a preview endpoint before the
user clicks, shows the route in text, and disables itself with a setup prompt when gated.

## 13. Deliver in slices with tests

**What happened.** Provider, routing, UI, and runtime integration were built as separate
slices, each with its own test. That made gaps visible early.

**Rule.** Follow the slices in `08`. Do not merge a slice without its test.
