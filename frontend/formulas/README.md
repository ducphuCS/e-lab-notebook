# Formulas — Intention Letter

> **Section:** Library · **Status:** resolved + implemented — all questions
> in §9 answered by the owner (2026-08-26); decisions recorded in §10.
> Formulas v0 implemented (service, gateway, overview + hidden detail pages,
> tests) — see the decision log for follow-ups.

## 1. Intention

Manage formulations and every aspect of one formulation. The Formulas page is
the source of truth for formulation master data — composition, params,
procedure — that the rest of the ELN builds on: Lab records batches and
samples produced from these formulas, and Analyze (DOE) drafts experiments
around them. The letter of intent for the page set:

The "Formulas" page consists of a set of pages. Each page has its own purpose:

1. Formulation overview
2. Formulation detail
3. Formulation create, update, delete and *duplicate* (prefer popup modal to
   actual full page)

Formulas are linked with batches and samples. Samples consist of test reports;
therefore, formulas are also linked with test reports.

## 2. Scope

**In scope**

- Formula overview — list of all formulas with attributes and stats.
- Formula detail — tabbed view: Overview, Composition, Params, Procedure,
  Documents, Versions.
- Create, update, delete and duplicate (modal preferred, see Q4). Deletion
  is blocked while the formula has linked batches or samples (delete policy,
  Q12).
- Per-formula custom fields (free key/value pairs, user-defined names).
- Links to batches, samples and test reports (read-only; counts/stubs until
  the Lab module lands, see §6).

**Out of scope (for now)**

- Calculation engine that *evaluates* params — v0 stores the param
  definition (source ingredient custom field + aggregation); evaluation is a
  later phase (Q3).
- Batch-size re-sizing / scaling tool (PROGRAM.md "calculation tools built
  into the Library" — later phase).
- Pricing estimation and constraints evaluation (PROJECT.md wish-list).
- Import/export.
- Approval workflow — status is a plain selectbox, no workflow enforcement
  (Q7).
- Versions beyond composition — v0 creates a new version only when the
  composition changes and diffs composition side-by-side; an explicit
  "save as a version" is deferred (Q2).
- Procedure / processing cost — formula cost is Σ ingredient costs only
  (owner: procedure cost is unnecessary complexity for now; Q8).
- Sub-ingredients / premixes — treat as regular ingredients in the master
  for now; re-discuss later (Q1).
- Procedure flow beyond linear — v0 shows a simple linear sequence of
  steps (no loops, no branches, no parallel steps); richer flows are
  re-discussed later (Procedure panel decision 2026-08-27).

## 3. User flows

- As a user I can see the full list of formulas with their attributes and
  stats.
- As a user I can open a formula and explore each aspect of it (composition,
  params, procedure, documents, versions).
- As a user I can create a new formula.
- As a user I can edit an existing formula.
- As a user I can delete a formula.
- As a user I can duplicate a formula (fast start for the next iteration).
- As a user I can see which batches, samples and test reports were produced
  from a formula.
- As a user I can read a formula's procedure as a simple linear graph and
  inspect each step's details (ingredients, equipment, duration, processing
  params) from the Procedure panel.
- As a user I can build a formula's procedure one step at a time: each
  step draws its subjects (ingredients) from the composition and carries
  its own equipment, duration and processing parameters (name/value/unit).

## 4. Layout

Two views — overview and detail — over one sidebar entry (Q5):

- **Overview** — full-width read-only table: formula id, name, project,
  status, family, updated date, and stats (number of ingredients, steps,
  batches, samples). Clicking the formula name opens the detail view.
- **Detail** — header (name, id, status) followed by tabs:
  - **Overview** — attributes + stats presented in detail; related batches,
    samples and test reports (with links when those pages exist).
  - **Composition** — table of ingredients: no, ingredient, role, amount,
    uom, percentage of total (derived, Q10), cost contribution (derived from
    ingredient unit cost, Q8), notes.
  - **Params** — theoretical params: parameter, value, and the formula used
    to calculate the parameter (Q3).
  - **Procedure** — the flow to produce samples from this formula, shown as
    a simple linear graph (nodes = steps, edges = execution order; no
    loops, no branches — for now). Three columns: the left lists the steps;
    the middle shows the top-to-bottom flow chart (graphviz); the right
    shows the details of the selected step. A step is its subjects
    (ingredients, more than one allowed) plus its attributes (equipment,
    duration, processing parameters — equipment-based by default,
    flexible).
  - **Documents** — attachments related to this formula (read-only list;
    Documents page owns attachments, Q6).
  - **Versions** — number of versions; a new version is created only when
    the composition changes. The tab compares two versions' composition
    side-by-side with highlighted differences (Q2).

Create / edit / delete / duplicate are dialogs launched from the overview
table and from the detail view (preferred over a full page, per the draft;
Q4, Q13). Empty states: "No formulas
yet — add your first one" on overview; per-tab placeholders when a tab has no
data.

## 5. Data

### 5.1 Schema (v0 — field decisions in §9)

| Field | Type | Required | Notes |
|---|---|---|---|
| id | integer | yes | Primary key, internal (auto-generated). |
| name | text | yes | Formula name. |
| project | text | no | Free text for v0 — the Projects module is a stub (Q9). |
| status | text | yes | draft \| active \| under review \| approved \| archived (selectbox, Q7). |
| family | text | no | Product family. |
| owner | text | no | Person in charge. |
| tags | json | no | Array of free tags. |
| description | text | no | |
| custom_fields | json | no | Per-formula key/value map (same pattern as Ingredients). |
| composition | json | no | Rows: {no, ingredient_id, role, amount, uom, notes}; percentage and cost contribution derived in UI (Q1, Q8, Q10). |
| params | json | no | Rows: {parameter, source (ingredient custom field), aggregation, value} — the definition is stored; evaluation is a later phase (Q3). |
| procedure | json | no | Steps: {name, ingredient_ids[], equipment, duration, params[{name, value, unit}]} — subjects are ingredients from the composition only; processing params are name/value/unit rows (Q11; panel decision 2026-08-27). |
| version | integer | yes | Current version number; a new version is created only when the composition changes (Q2). |
| created_at | text | yes | ISO timestamp. |
| updated_at | text | yes | ISO timestamp. |

**Derived-value rule:** percentage of total and cost contribution are never
stored — they are computed in the UI from the composition and ingredient
master data, guarded by a same-unit rule (all rows must share one uom,
otherwise "—" is shown). Params follow the same spirit: the definition is
stored, the value is computed later (Q3, Q8, Q10).

### 5.2 Persistence (resolved — follows the Ingredients precedent, Q2 in that letter)

SQLite mockup via stdlib `sqlite3` + pandas (no SQLAlchemy). DB-access code
in `backend/services/formulas/`; dev DB file in the repo
(`backend/services/formulas/data/formulas.db`), already gitignored via `*.db`
(root `.gitignore`). Tests use temp/in-memory DBs, never the dev DB. Service
is deliberately dumb (no validation); validation lives in a shared module,
the gateway validates requests/responses (per `docs/TEST_STRATEGIES.md`).

## 6. Dependencies on other modules

- **Ingredients** (Library): composition rows reference ingredients by id —
  this is what fills the placeholder "Formulas using this ingredient" metric
  on the Ingredients details panel (currently hardcoded `"0"`). When
  Formulas lands, the ingredient master also gains a unit-cost field (cost
  per uom) — see the Ingredients letter decision log (Q8). Keep field
  naming consistent (item code / item description).
- **Projects** (Overview): `project` is free text until Projects lands (Q9).
- **Batches** (Lab, live since 2026-09-03): batches are produced *from* a
  formula — `formula_id` is stored on the batch (that letter's Q1). The
  Formulas detail Overview tab lists the related batches (real counts via
  the Batches service, with links into batch detail), and the overview
  table's "batches" column is a real count; the delete guard (Q12) now
  blocks deleting a formula that batches reference. Page-layer
  cross-service reads via `dialogs.batches_connection()` (one session
  connection; decision log 2026-09-03).
- **Samples / Test reports** (Lab, stubs): reachable through batches; same
  placeholder treatment until those modules land (the delete guard and
  stats extend then).
- **Documents** (Library, stub): owns attachments; the Documents tab shows a
  read-only list of linked documents (Q6).
- **Equipment** (Library, stub): procedure steps reference equipment by name
  as free text for v0 (Q11).
- **DOE** (Analyze): DOE drafts formulations as item_code / item_description /
  uom / m_0. When Formulas lands, DOE can link drafts to real formulas — keep
  ingredient naming consistent so the bridge is cheap.

## 7. UX / widget choices

- **Overview table**: read-only `st.dataframe` with row selection, mirroring
  Ingredients (row selection + explicit actions, not inline editing — the
  deliberate divergence from the DOE `st.data_editor` pattern, see Ingredients
  README §7).
- **Create / edit / delete / duplicate**: `st.dialog` modals (draft's stated
  preference) — a deliberate divergence from Ingredients' right-panel form.
  Dialogs launch from the overview table and from the detail view (header
  Edit button; per-tab edit for composition and procedure) (Q4, Q13).
- **Detail navigation**: a hidden child page (`st.Page(..., visibility=
  "hidden")`, streamlit ≥ 1.60) switched via `st.switch_page`; the formula
  id travels in `st.query_params` (`?formula_id=3`) so URLs are shareable;
  "← Back to overview" clears the param. Chosen over internal-switch and
  inline options so the six-tab detail view stays a separate thin file
  (AGENTS.md §5 page-folder pattern) and the sidebar stays unchanged (Q5).
- **Composition editor**: `st.data_editor` rows inside the create/edit dialog;
  ingredient column is a selectbox over the Ingredients master (Q1).
- **Procedure panel** — three columns: left = selectable step list
  (radio); middle = top-to-bottom flow chart of the steps; right = details
  of the selected step. Steps are added/edited **one at a time** via
  `st.dialog` modals (create/edit/delete step); the subjects (ingredients)
  are multi-selected **from the composition only**; processing parameters
  are name/value/unit rows. The flow chart is a linear sequence for v0 (no
  loops/branches, §2), built with the `graphviz` Python package and
  rendered with Streamlit's built-in `st.graphviz_chart` (dagre-d3 renders
  client-side — no system Graphviz binary needed). The create/edit dialog
  no longer carries params/procedure (2026-08-27, §10).
- **Validation** extracted into plain functions (frontend utils + backend
  validation), following the DOE `validators.py` / Ingredients `utils.py`
  pattern; pages stay thin glue (per `docs/TEST_STRATEGIES.md` §5).

## 8. Testing

Mirrors the Ingredients test layout (`docs/TEST_STRATEGIES.md`):

- **Unit — service:** formulas store CRUD + validation in
  `tests/unit/backend/` (temp/in-memory DB, no network) — including the
  version-snapshot trigger (a new version only when composition changes).
- **Unit — frontend:** pure utils (composition payload builder, stats
  computation, percentage derivation) in `tests/unit/frontend/`.
- **Contracts:** gateway request/response validation against golden JSON
  fixtures with mocked transport (`tests/contracts/`).
- **App behavior:** `tests/app/test_formulas_page.py` with the gateway
  **faked** at the boundary (mirrors `tests/app/test_ingredients_page.py`).
  Note: streamlit 1.60's `testing.v1` has no `st.dialog` support, so dialog
  *submission* flows (create/edit/delete/duplicate) are not drivable from
  AppTest — they are covered by the service/gateway/contract tests and the
  frontend utils tests instead. AppTest covers page loads, rendering, and
  dialog opening (see decision log 2026-08-26).

## 9. Questions & Resolutions

### Q1. Composition — how do rows reference ingredients?

- **Status:** resolved 2026-08-26
- **Context:** the Ingredients details panel shows a placeholder metric
  "Formulas using this ingredient" (`"0"`). That count only becomes real if
  composition rows point at ingredients by id. PROJECT.md also allows
  "sub-ingredients" (premixes), which may not exist in the ingredient master.
- **Options:** (a) rows reference ingredient id only, selected from the
  Ingredients master; (b) free-text item_code/item_description only (like
  DOE drafts today); (c) hybrid — ingredient id with a free-text fallback.
- **Recommended resolution:** (a) for v0 — ingredient id + a denormalized
  name snapshot for display. Keeps one vocabulary, powers the reverse count,
  and the hybrid case can be added later without schema churn.
- **Answer**: Option (a) is fine. Sub-ingredients (premixes) can be treated like an ingredient in the master as well, but this is top-of-mind, note that we will discuss later.

### Q2. Versions — how much versioning in v0?

- **Status:** resolved 2026-08-26
- **Context:** the Versions tab shows "the number of versions and the
  differences between them". Full snapshot-diffing on every save is the most
  faithful reading but the heaviest.
- **Options:** (a) every update appends a snapshot row; UI shows the list and
  a field-level "what changed" summary; (b) version number + updated_at +
  change note only (no diff); (c) explicit "save new version" button, no
  auto-snapshotting.
- **Recommended resolution:** (a) — snapshot table
  (`formula_versions`: formula_id, version, snapshot JSON, created_at,
  change_note), field-level diff in the UI. Satisfies the draft's intent with
  a small, dumb store.
- **Answer**: I am confused. Do you talk about versioning when edit/duplicate a formula? My intention for tab Version is to show how many versions this fomula has, show the composition side-by-side and highlight the difference. We can discuss it.
- **Resolution:** v0 — a new version is created **only when the composition
  changes**; edits to name/status/params/procedure update the current
  version in place, and a status-only change never creates a version. The
  snapshot table stores the full formula record at the moment of a
  composition change; the Versions tab shows the version count and diffs
  composition side-by-side with highlighted differences. An explicit
  "save as a version" was noted as interesting and deferred to a later
  phase.

### Q3. Params — is the "formula" evaluated or documented?

- **Status:** resolved 2026-08-26
- **Context:** params carry "parameter, value, and the formula to calculate
  the parameter". PROGRAM.md promises calculation tools, but an evaluation
  engine is a project of its own.
- **Recommended resolution:** v0 stores the formula as documentation text and
  the value as entered; no evaluation. The calculation engine is a later
  phase built on the same stored formula strings. (Keeps §2 "out of scope"
  honest.)
- **Answer**: When I said calculate formula theoretical parameter, I mean ingredients may have shared custom field, e.g., brix, then the theoretical "brix" of the formula can be the sum of these custom fields. I am agree with you that the calculation engine should be dealt with later, after we complete a certain level for the pages.
- **Resolution:** params store the definition — {parameter, source
  ingredient custom field, aggregation (e.g. sum), value} — e.g. theoretical
  brix = Σ ingredient brix custom fields. No evaluation in v0; the
  calculation engine is a later phase built on the stored definitions.
  Exact aggregation semantics (sum vs weighted) are decided when the engine
  lands.

### Q4. Create/edit/delete/duplicate — modal vs ingredients-style panel?

- **Status:** resolved 2026-08-26
- **Context:** the draft prefers popup modals over full pages; Ingredients
  uses a right-panel form (deliberate divergence from DOE). `st.dialog` is a
  built-in (streamlit >= 1.60) so modals are available.
- **Recommended resolution:** keep the draft's preference — `st.dialog`
  modals. Record as a conscious divergence from Ingredients, same as
  Ingredients' divergence from DOE.
- **Answers** Yes, keep the draft's preference for modal/dialog.

### Q5. Detail navigation — how does "click the name → detail" work?

- **Status:** resolved 2026-08-26
- **Context:** the router registers one `formulas/app.py` page. Options:
  (a) internal view switch (overview ⇄ detail) in the same file, id in
  `st.query_params` (shareable URL); (b) a second hidden child page +
  `st.switch_page`; (c) detail rendered below the table on the same page.
- **Recommended resolution:** (a) — one registered page, internal switch,
  query param `?formula_id=` so the URL survives reruns and can be shared.
  No router/nav changes needed.
- **Answer** I can't picture the differences right now. I will give your recommendation a try. I may need a more detailed comparision between options.
- **Resolution:** option (b) — a hidden child page. `st.Page(
  "formulas/detail.py", visibility="hidden")` is natively supported in
  streamlit ≥ 1.60; the overview switches via `st.switch_page` and passes
  the formula id in `st.query_params` (`?formula_id=3`), so URLs are
  shareable. "← Back to overview" clears the param. Chosen over the
  internal-switch and inline options because the six-tab detail view stays a
  separate thin file (AGENTS.md §5 page-folder pattern) and the sidebar
  stays unchanged.

### Q6. Documents tab — who owns attachments?

- **Status:** resolved 2026-08-26
- **Context:** Ingredients explicitly excludes attachments ("Documents page
  owns attachments"). The Formulas draft lists a Documents tab.
- **Recommended resolution:** follow Ingredients — Documents page owns
  attachments; the Formulas Documents tab shows a read-only list of
  documents linked to this formula (placeholder until Documents lands).
  Avoids two competing upload paths.
- **Answer**: I am okay with Documents owning the documents.

### Q7. Status — enum + workflow?

- **Status:** resolved 2026-08-26
- **Context:** draft lists draft | active | under review | approved |
  archived. No statement about who may change it or what transitions are
  legal.
- **Recommended resolution:** v0 = plain selectbox with the five values, no
  workflow enforcement; approval workflow is out of scope (§2). Free-text
  transition rules can be layered on later without schema change.
- **Answer**: This is an idea for now. Keep it as selectbox. We may come back to it when we approach authorization.

### Q8. Costs in Composition — where does cost come from?

- **Status:** resolved 2026-08-26
- **Context:** the Composition tab lists "costs", but the ingredient schema
  has no cost field, and there is no pricing source.
- **Recommended resolution:** show "—" placeholder in v0; add a cost field to
  the ingredient master (or a pricing source) in a later phase. Keeping a
  per-row cost input on the formula would duplicate data with no source of
  truth.
- **Answer**: The cost can be the sum of the cost of each ingredient in the formula and, in some case, the cost of the procedure. We should add a cost field to the ingredient master.
- **Resolution:** the ingredient master gains a unit-cost field (cost per
  uom, e.g. $/kg) when Formulas lands — a coordinated change, see the
  Ingredients letter decision log (2026-08-26). Formula cost =
  Σ(amount × unit cost) over composition rows (per-row contribution + total),
  guarded by the same-unit rule (row uom must match the ingredient's cost
  uom, otherwise "—"). Procedure/processing cost is out of scope for now
  (owner: unnecessary complexity); re-discuss later.

### Q9. Project — text or FK?

- **Status:** resolved 2026-08-26
- **Context:** `project` is listed in overview attributes and create form;
  the Projects module is a stub.
- **Recommended resolution:** free text for v0; switch to a project id FK
  when Projects lands (schema note already says so).
- **Answer**: Your suggestion seems fine

### Q10. Percentage of total — stored or derived?

- **Status:** resolved 2026-08-26
- **Context:** Composition shows "percentage of total"; amounts carry
  per-row uom, so a naive sum mixes units.
- **Recommended resolution:** derive in the UI as mass % (amount / total)
  only when all rows share one uom; otherwise show "—". Never stored — it
  would drift when composition changes.
- **Answer**: I'm fine with this.

### Q11. Procedure — equipment as text or FK?

- **Status:** resolved 2026-08-26
- **Context:** steps reference equipment; the Equipment module is a stub.
- **Recommended resolution:** free-text equipment name for v0; FK when
  Equipment lands (same pattern as Q9).
- **Answer**: Same as Q10. I'm fine with this.

### Q12. Delete policy — what happens to a formula that has linked data?

- **Status:** resolved (v0) 2026-08-26 — revisit when Lab lands
- **Context:** a formula is linked to batches and samples; deleting it would
  orphan that record chain. The owner is reluctant to delete a formula that
  has such links.
- **Resolution:** deletion is blocked while the formula has linked batches
  or samples (the delete dialog explains why). In v0 the links are
  placeholders (counts = 0) so deletion always proceeds; the guard and its
  UX are re-discussed when the Lab module lands.

### Q13. Edit entry points — where do the dialogs launch from?

- **Status:** resolved 2026-08-26
- **Context:** the letter said create/edit/delete/duplicate dialogs sit on
  the overview; the owner noted that editing from the detail view is
  natural too (e.g. adjusting composition from its tab).
- **Resolution:** dialogs launch from both — the overview table row actions
  and the detail view (header Edit button; per-tab edit for composition and
  procedure). One dialog implementation is reused from both entry points.

## 10. Decision Log

*Record answers and design decisions with dates. Keeps the letter as the
source of truth as it evolves.*

| Date | Decision | By |
|---|---|---|
| 2026-08-26 | Letter restructured to the Ingredients template (§1–§10); draft content preserved; open questions listed in §9 with recommended resolutions | ducphu |
| 2026-08-26 | Persistence: SQLite mockup in `backend/services/formulas/`, dev DB gitignored via existing `*.db` rule (resolved — follows Ingredients Q2 / TEST_STRATEGIES precedent) | ducphu |
| 2026-08-26 | Testing: mirror Ingredients — service unit, frontend utils unit, gateway contracts, AppTest with faked gateway (resolved — follows TEST_STRATEGIES) | ducphu |
| 2026-08-26 | All §9 questions answered by the owner; Q1–Q11 resolved, Q12 (delete policy) and Q13 (edit entry points) added | ducphu |
| 2026-08-26 | Versioning: new version only on composition change; status-only edits never bump; Versions tab = count + composition side-by-side diff; "save as a version" deferred | ducphu |
| 2026-08-26 | Costs: unit cost per uom added to the ingredient master when Formulas lands; formula cost = Σ(amount × unit cost) with same-unit guard; procedure cost out of scope | ducphu |
| 2026-08-26 | Navigation: hidden child page (`visibility="hidden"`) + `st.switch_page`, formula id via `st.query_params` | ducphu |
| 2026-08-26 | Finding: streamlit 1.60 `testing.v1` has no `st.dialog` support — dialog submission flows are covered at the service/contract/utils layers; AppTest covers loads/rendering/dialog-opening (README §8) | ducphu |
| 2026-08-27 | Edit dialog slimmed: the Params and Procedure editors were removed from the create/edit dialog (the gateway merges the payload over the current record, so existing values are preserved); each gets its own panel editor later | ducphu |
| 2026-08-27 | Procedure panel design: two columns — left (wider) step list, right = graph + details of the selected step; the graph is a simple linear sequence (no loops, no branches) for now; each step = its subjects (ingredients) + its attributes (equipment, duration, processing params) | ducphu |
| 2026-08-27 | Procedure step schema: processing params are now a list of {name, value, unit} (was a key→value string map); step subjects (ingredients) are constrained to the composition — a step can never introduce an ingredient the formula does not contain | ducphu |
| 2026-08-27 | Procedure panel implemented: left (wider) selectable step list + right linear-flow SVG graph and selected-step details; steps added/edited/deleted one at a time via st.dialog; graph is a built-in st.html inline SVG (no graphviz dependency) | ducphu |
| 2026-08-27 | Procedure panel: three columns — left step list, middle top-to-bottom flow chart, right step details. Flow chart via the `graphviz` Python package + Streamlit's built-in `st.graphviz_chart` (dagre-d3 renders client-side, no system binary); `graphviz>=0.19` added to `pyproject.toml` (owner-approved) — supersedes the hand-rolled SVG | ducphu |
| 2026-09-03 | Batches reverse link live: Batches service gained `list_batches_by_formula` (light summaries) + `count_batches_by_formula_id` (one GROUP BY); Formulas overview "batches" column and detail Overview "related batches" are real counts with links into batch detail; Q12 delete guard now blocks deleting a formula that batches reference — enforced in the delete dialog (`delete_block_reason` pure helper), since the condition lives in another service; samples/test reports stay placeholders until those modules land | ducphu |
| 2026-09-09 | Formulas v0 marked implemented: this README's header said "implementation not started" although the module landed 2026-08-26 (service, gateway, overview + hidden detail pages, tests); header updated to reflect the real state (mirrors the Batches header fix 2026-09-09). Open items: the Q8 ingredient unit-cost field + formula cost contribution are still **not implemented** (no cost column in the Composition tab — `detail.py` defers to this letter), and the "Formulas using this ingredient" metric on Ingredients remains a hardcoded "0" (see the Ingredients letter decision log 2026-09-09) | ducphu |
| 2026-09-09 | Relationship reminder captions (mirrors the Batches letter decision log 2026-09-09): Formulas overview caption under the page title + detail Composition tab note — batches made from a formula freeze their planned composition at creation (a snapshot of the formula, scaled to each batch's target yield); later formula edits never change existing batches | ducphu |
