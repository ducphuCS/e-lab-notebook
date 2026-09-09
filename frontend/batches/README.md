# Batches — Intention Letter

> **Section:** Lab · **Status:** resolved + implemented — all questions in §9
> (Q1–Q8) answered by the owner (2026-09-03); decisions recorded in §10.
> Batches v0 implemented (service, gateway, overview + hidden detail pages,
> tests) — see the decision log for follow-ups.

## 1. Intention

The owner's draft says it plainly:

> 1. Batches is where the lab actually happens. Based on a pre-defined
>    formula, batches are created to record the actual lab works, such as the
>    actual amount of ingredients, the actual processing parameters, etc.
> 2. Batches are required to have their names and ids.
> 3. Later, batches will produce samples and hence also produce test
>    reports.

Batches is the Lab module's record of **what actually happened — not what was
planned** (PROGRAM.md §4.3). A batch is a concrete run of a pre-defined
formula: the formulator creates it *from* a formula in the Library, turns it
into a **plan** for a target batch size (Q3), then records the run as it
happens — actual amounts of ingredients, actual yield, observations,
deviations. Where Formulas holds the intended master recipe, Batches holds
the record of reality.

A batch is also the head of the traceability chain *formula → batch → sample →
test report* (PROGRAM.md §4, IDEAS.md #10): samples are taken from the batch
and carry its identity everywhere they go; test reports attach to the samples.
Months later, anyone can open a batch and read its full story.

## 2. Scope

**In scope**

- Batch overview — list of all batches with attributes and stats.
- Batch detail — the recorded story of one run, built around **planned vs
  actual**.
- Create a batch from a formula: pick the formula, set a **target yield**,
  and the planned ingredient amounts scale to that target — the batch is
  born as a plan (Q1, Q3).
- User-visible identity — every batch has a name and an id (Q4).
- A lifecycle selectbox, defaulting to *planned* (Q5).
- Recording actuals when the run happens: one actual amount per ingredient
  (formulators weigh ingredients first), actual yield, observations /
  deviation notes (Q2). Processing actuals are **not** recorded in v0 —
  step-by-step execution logging comes later (Q2, Q8).
- Links to the formula (upstream) and to samples / test reports (downstream,
  read-only counts/stubs until Samples lands — same treatment as Formulas).
- Delete, allowed only while the batch is *planned* with no linked samples
  or test reports (Q6).

**Out of scope (for now)**

- Batch-size re-sizing / scaling **calculation tool** — belongs to Library
  (PROGRAM.md "calculation tools built into the Library"; Formulas letter §2
  defers it). The v0 batch plan scales by a plain factor from the formula
  (Q3); the real tool replaces it when it lands.
- Step-by-step procedure *execution logging* (who did what, at what time, per
  procedure step, actual processing values per step) — the owner wants this
  shape eventually (Q2) but it is not v0; revisit when the batch/procedure
  data is mature (Q8).
- Printing the scaled plan for weighing — the owner noted this as a "come
  back later" idea (Q3).
- Attachments (photos, COA, printed charts) — Documents page owns
  attachments.
- Import/export.
- Approval workflow — status is a plain selectbox, no workflow enforcement
  (mirrors Formulas Q7).
- Unit conversion — the plan scales only when all planned amounts share one
  uom (same-unit guard, §5.1); no conversions in v0.
- Overview-timeline features for the Dashboard — batches will feed that
  module later; it is out of scope here.
- Versioning / field-level history of the batch record itself — created_at /
  updated_at only in v0.

## 3. User flows

- As a user I can see the full list of batches with their attributes and
  stats.
- As a user I can create a batch from a formula: set the target yield and
  the planned ingredient amounts scale accordingly — the batch starts as a
  *planned* plan, ready to weigh against.
- As a user I can record a run as it happens: actual amount per ingredient,
  actual yield, observations.
- As a user I can see planned vs actual side by side, so deviations are
  visible at a glance.
- As a user I can advance a batch through its lifecycle (*planned* → *in
  progress* → *completed*).
- As a user I can open a batch and read its full story — including which
  samples and test reports were produced from it.
- As a user I can edit an existing batch.
- As a user I can delete a *planned* batch that has no samples or test
  reports (delete policy, Q6).

## 4. Layout

Two views — overview and detail — over the single Lab sidebar entry
(mirrors Formulas, Q5 in that letter):

- **Overview** — full-width read-only table: batch code (B-####), name,
  formula, status, created/updated dates, and stats (target/actual yield,
  number of samples and test reports). Clicking the batch code/name opens the
  detail view.
- **Detail** — header (batch code, name, status) followed by tabs:
  - **Overview** — the batch at a glance: formula it was made from (link to
    the formula detail page), formula version used, target yield, actual
    yield, status, observations, and related samples / test reports (with
    links when those pages exist).
  - **Composition** — planned vs actual, one row per ingredient: no,
    ingredient, planned amount + uom (scaled to the target yield), actual
    amount + uom, deviation (derived when the units match, same-unit rule —
    mirrors Formulas Q10), notes.
  - **Processing** — the planned processing parameters from the formula
    snapshot, shown read-only for reference. Actual processing values are
    **not** recorded in v0; this tab grows actuals with the step-by-step
    execution log later (Q2, Q8).
  - **Samples** — read-only list/count of samples produced from this batch
    and their test reports (placeholders until Samples / Test Reports land).

Create / edit / delete launch from the overview and the detail view.
Empty states: "No batches yet — create one from a formula" on overview;
per-tab placeholders when a tab has no data.

## 5. Data

### 5.1 Schema (v0 — field decisions in §9, all resolved 2026-09-03)

| Field | Type | Required | Notes |
|---|---|---|---|
| id | integer | yes | Primary key, internal (auto-generated). |
| batch_code | text | yes | User-visible id `B-####` (PROGRAM.md style), auto-generated sequential, read-only after creation (Q4). |
| name | text | yes | Batch name (human-friendly title) (Q4). |
| formula_id | integer | yes | Formula this batch was made from (Q1). |
| formula_name | text | yes | Denormalized formula name at creation — what the batch was made from, shown in overview/detail; identity and navigation follow `formula_id` (Q1). |
| formula_version | integer | yes | Formula version pinned at creation (Q1). |
| planned | json | yes | Snapshot taken at creation: target yield + composition scaled to it + the formula's processing params. The plan actuals are compared against (Q1, Q3). |
| actual | json | no | Recorded when the run happens: one actual amount per ingredient (Q2), actual yield, observations. No processing actuals in v0 (Q2, Q8). |
| status | text | yes | planned \| in progress \| completed — plain selectbox, default *planned*, no workflow (Q5). |
| owner | text | no | Person in charge of the run. |
| created_at | text | yes | ISO timestamp. |
| updated_at | text | yes | ISO timestamp. |

Row shapes (v0):

- `planned.composition` — scaled rows `{no, ingredient_id, amount, uom}`:
  the formula's composition amounts × factor, where
  factor = target yield ÷ Σ formula amounts. The rows keep the ingredient
  ids so actuals can line up row by row.
- `planned.target_yield` — `{amount, uom}`, what the batch aims to make.
- `planned.processing` — snapshot of the formula's processing params /
  procedure (read-only reference in v0; the base for the future execution
  log, Q2).
- `actual.composition` — rows `{ingredient_id, amount, uom, note}` — one
  actual amount per ingredient, aligned to the planned rows; absent until
  recorded.
- `actual.yield` — `{amount, uom}`; `actual.observations` — free text.

**Derived-value rule:** deviation (planned vs actual) is computed in the UI
and never stored; it shows only when the planned and actual uom match,
otherwise "—" (mirrors Formulas Q10). The same guard applies to scaling:
planned amounts scale only when every composition row shares one uom and the
target yield is entered in that uom — no unit conversion in v0 (§2); when
units are mixed the plan rows are entered/adjusted manually instead. Actual
cost per batch (actual amounts × ingredient unit cost) is a later phase —
see §6.

### 5.2 Persistence (resolved — mirrors Ingredients Q2 / Formulas precedent)

SQLite mockup via stdlib `sqlite3` + pandas (no SQLAlchemy). DB-access code
in `backend/services/batches/`; dev DB file in the repo
(`backend/services/batches/data/batches.db`), already gitignored via the
existing `*.db` rule (root `.gitignore` — no new rule needed). Tests use
temp/in-memory DBs, never the dev DB. Service is deliberately dumb (no
validation); validation lives in a shared module; gateway validates
requests/responses (per `docs/TEST_STRATEGIES.md`).

## 6. Dependencies on other modules

- **Formulas** (Library): a batch is created *from* a formula — `formula_id`
  + pinned version + planned snapshot (Q1). The Formulas detail Overview tab
  shows the related batches — real counts and links since 2026-09-03, each
  row also carrying the pinned formula version since 2026-09-09 (decision
  log below). Formulas' delete guard (that letter's Q12) blocks deleting a
  formula that batches reference (live since 2026-09-03) — mirroring
  Batches' own delete guard (Q6). The batch → formula back-link decision is
  this letter's Q1 (the Formulas letter §6 defers it here).
- **Ingredients** (Library): planned and actual composition rows reference
  ingredients by id — one vocabulary, same pattern as Formulas composition
  (Q1 in that letter). When a later phase derives *actual* batch cost, actual
  amounts × ingredient unit cost (the cost field planned with Formulas, see
  Ingredients letter decision log 2026-08-26) supply it.
- **Samples** (Lab, stub): a batch produces samples; the detail Samples tab
  shows counts/links. Sample-side link mechanics (can a sample exist without
  a batch? PROJECT.md researchers "work with samples with or without
  knowledge about the formulations behind") are decided in the Samples
  letter. The delete guard (Q6) reads the sample/test-report links.
- **Test reports** (Lab, stub): produced for the samples of a batch;
  reachable through the batch's samples.
- **Documents** (Library, stub): owns attachments; batches carry no upload
  path (out of scope, §2).
- **Dashboard / Overview**: the Overview module's project timeline shows
  batches (PROGRAM.md §4.1 example: "four batches on the timeline") — a
  future consumer of batch data, out of scope for this letter.

## 7. UX / widget choices

- **Overview table**: read-only `st.dataframe` with row selection and explicit
  actions, mirroring Ingredients/Formulas (the deliberate divergence from the
  DOE `st.data_editor` pattern — Ingredients README §7).
- **Create / edit / delete**: `st.dialog` modals (the Formulas draft's stated
  preference, Formulas Q4). The create-from-formula dialog walks: pick
  formula → enter target yield → preview the scaled plan (planned amounts,
  status *planned*) → save.
- **Detail navigation**: a hidden child page (`st.Page(..., visibility=
  "hidden")` + `st.switch_page`, batch id in `st.query_params` as
  `?batch_id=`), following the Formulas precedent (Q7).
- **Planned vs actual display**: side-by-side columns for composition rows;
  deviation derived under the same-unit rule (§5.1). Processing tab shows
  planned values read-only in v0 (Q8).
- **Validation** extracted into plain functions (frontend utils + backend
  validation), following the DOE `validators.py` / Formulas `utils.py`
  pattern; pages stay thin glue (per `docs/TEST_STRATEGIES.md` §5). Scaling
  (factor computation, same-unit guard) is a pure util.

## 8. Testing

Mirrors the Ingredients/Formulas test layout (`docs/TEST_STRATEGIES.md`):

- **Unit — service:** batches store CRUD + validation in `tests/unit/backend/`
  (temp/in-memory DB, no network) — including the planned snapshot taken at
  creation (Q1) and the delete guard (status *planned* + no linked
  samples/test reports, Q6).
- **Unit — frontend:** pure utils (planned-snapshot builder incl. target-yield
  scaling + same-unit guard, deviation computation, stats) in
  `tests/unit/frontend/`.
- **Contracts:** gateway request/response validation against golden JSON
  fixtures with mocked transport (`tests/contracts/`).
- **App behavior:** `tests/app/test_batches_page.py` with the gateway
  **faked** at the boundary (mirrors the ingredients/formulas page tests).
  Same caveat as Formulas: streamlit 1.60's `testing.v1` has no `st.dialog`
  support, so dialog *submission* flows are covered at the
  service/gateway/contract/utils layers; AppTest covers loads, rendering and
  dialog opening.

## 9. Questions & Resolutions

### Q1. Batch ↔ formula — live reference or planned snapshot?

- **Status:** resolved 2026-09-03
- **Context:** the draft says a batch is "based on a pre-defined formula".
  The Formulas letter §6 defers the back-link (batch → formula) to this
  letter, and its delete guard (Q12) needs the link to be real. Formulas are
  editable and versioned (a new version on composition change) — so "what
  the batch was made from" can drift if read live. Traceability (PROGRAM.md)
  demands a batch's story stays readable forever.
- **Options:** (a) `formula_id` only — composition read live from the formula;
  (b) full planned snapshot copy at creation, formula reference for
  navigation only; (c) `formula_id` + pinned `formula_version` +
  denormalized planned snapshot of composition/procedure/params.
- **Recommended resolution:** (c).
- **Answer**: Option (c) seems fine
- **Resolution:** a batch always references exactly one formula (required at
  creation), pins `formula_version`, and stores the planned composition +
  processing params as a snapshot inside the batch (§5.1). Later formula
  edits never rewrite a batch's history; actuals are recorded against the
  snapshot.

### Q2. What does "actual" mean in v0 — totals, or per-step execution?

- **Status:** resolved 2026-09-03 (processing actuals deferred — see Q8)
- **Context:** the draft records "actual amounts of ingredients, actual
  processing parameters". A batch runs over time and the formula's procedure
  has steps, each with its own params (equipment, duration, processing
  params). Recording *execution* (per step: actual duration, actual params at
  each step, who/when) is the faithful reading but the heaviest.
- **Options:** (a) end-of-batch actuals only — one actual amount per
  ingredient, one actual value per processing parameter, actual yield,
  observations; (b) per-step execution log attached to the formula's
  procedure steps.
- **Recommended resolution:** (a) for v0.
- **Answer**: (a) is okay. Usually, formulators weigh all the ingredient
  first, then conduct the batches. So one actual amount per ingredient is
  fine. So is the actual yield. About the processing values, I want a
  step-by-step execution logging, but reckon it may not be the time. Note it
  so we can come back later.
- **Resolution:** actuals in v0 = one actual amount per ingredient (weighing
  happens up front, so a flat per-ingredient record matches the real
  workflow), actual yield, and observations. Processing values split off
  from option (a): the owner wants them captured **per procedure step** as an
  execution log, and defers that feature — see Q8 for what v0's Processing
  tab does meanwhile. Recorded as a "come back later" item in the decision
  log.

### Q3. Batch plan — how do planned quantities get to the target size?

- **Status:** resolved 2026-09-03
- **Context:** PROGRAM.md's story is "the formulator picks the formula; the
  calculation tool recalculates the recipe for the target batch size" — but
  that tool is a later Library phase (Formulas §2 out of scope). A batch
  still has an implicit size (a 100 kg run vs a 2 kg lab batch), and users
  need numbers they can weigh against.
- **Options:** (a) planned quantities copied from the formula as-is; batch
  size recorded as a plain attribute (text/amount); (b) the batch carries a
  simple scale factor that multiplies every planned amount in the UI; (c)
  wait for the real calculation tool.
- **Recommended resolution:** (b).
- **Answer**: A simple scaler seems fine. Users definitely need something to
  calculate. My idea is that from the planned value (from formula), we allow
  users to set a target yield and scale the ingredients accordingly. This can
  be treated like a plan. Users may want to print it so that they can weigh
  easier but we will back to this later.
- **Resolution:** the batch's plan is the formula's composition **scaled to a
  target yield the user sets at creation** (planned rows stored scaled, per
  Q1's snapshot). This is the batch's working plan — what the formulator
  weighs against. Scaling factor = target yield ÷ Σ formula amounts, valid
  only under the same-unit guard (§5.1; mixed units → plan rows entered
  manually). The real Library calculation tool replaces this when it lands.
  Printing the scaled plan for easier weighing is noted and deferred
  (decision log 2026-09-03).

### Q4. Identity — what are "name and id" exactly?

- **Status:** resolved 2026-09-03
- **Context:** every record has an internal auto-increment PK, so "batches
  are required to have names and ids" must mean a *user-visible* identity —
  PROGRAM.md's example is "batch B-0142". Notebook-style ids carry weight in
  a lab (they get written on jars, shared in emails).
- **Options:** (a) user-typed id, e.g. a lab notebook code, validated unique;
  (b) auto-generated sequential id `B-####` (read-only, like a notebook
  number) + required user name; (c) internal id only, name required.
- **Recommended resolution:** (b).
- **Answer**: I think option (b) is good.
- **Resolution:** auto-generated sequential `batch_code` (`B-####`, e.g.
  `B-0142`), displayed prominently (overview id column + detail header),
  never editable after creation; plus a required free-text `name`. Ids are
  collision-free and human-readable with zero typing burden.

### Q5. Status — does a batch have a lifecycle?

- **Status:** resolved 2026-09-03
- **Context:** a batch is born as a plan (Q3), then recorded *as it happens*
  (over time) and finished. The owner's Q6 answer introduces *planned* as a
  state the batch starts in and can be deleted from.
- **Options:** (a) no status — the batch is simply open for edits; (b) a
  plain selectbox; (c) full workflow.
- **Recommended resolution:** (b) with a minimal set.
- **Answer**: Selectbox is okay to start with.
- **Resolution:** statuses **planned | in progress | completed**, plain
  selectbox, default *planned* (a created batch is a plan — Q3), no workflow
  enforcement (mirrors Formulas Q7). The delete guard keys off *planned*
  (Q6). "Completed" ≈ "the batch has samples/test reports" in practice
  (owner's note, Q6); a batch that ends without producing samples is marked
  *completed* manually.

### Q6. Delete policy — and is duplicate needed?

- **Status:** resolved 2026-09-03
- **Context:** Formulas resolves deletion-block-while-linked (Q12). A batch
  links upstream to a formula and downstream to samples/test reports.
  Deleting a batch would orphan its samples' identity chain. The owner's
  repeated-work pain (PROGRAM.md §2.5) is about *incomplete* records, not
  about re-keying batches of the same formula.
- **Options:** (a) deletion allowed freely; (b) deletion blocked while the
  batch has linked samples/test reports; duplicate action offered; (c)
  delete blocked only once completed, or soft-delete.
- **Recommended resolution:** (b) — no duplicate in v0.
- **Answer**: The batches can only be deleted if their status is planned and
  there is no related sampels or test reports. Duplication is not required as
  you said. I note that the "batch is completed" and "the batch has samples
  or test reports" are the same.
- **Resolution:** deletion is allowed only while the batch is **planned**
  (status) **and** has no linked samples or test reports — the delete dialog
  explains why when blocked (mirrors Formulas Q12). The two conditions are
  near-equivalent in practice (a batch that produced samples is *completed*),
  but both are enforced so a status accidentally set back to *planned* cannot
  orphan sample chains. No duplicate action in v0 — the natural "next run of
  the same formula" flow is *create batch from formula* again (re-discuss
  when real usage shows the pain).

### Q7. Detail navigation — follow the Formulas precedent?

- **Status:** resolved 2026-09-03
- **Context:** Formulas resolved detail navigation as a hidden child page +
  `st.switch_page` + `?formula_id=` (that letter's Q5) so the tabbed detail
  view stays a separate thin file. Batches' detail is the same shape (header
  + tabs + related data).
- **Recommended resolution:** follow the Formulas precedent.
- **Answer**: I am okay with this.
- **Resolution:** `st.Page("batches/detail.py", visibility="hidden")`,
  `?batch_id=` in query params, shareable URLs, "← Back to overview" clears
  the param. Consistency across modules keeps the router and sidebar
  unchanged.

### Q8. Processing actuals in v0 — flat, or none until the execution log?

- **Status:** resolved 2026-09-03
- **Context:** Q2 resolves that processing values should eventually be
  recorded as a **step-by-step execution log** (per procedure step), which
  the owner defers. That leaves open what — if anything — v0 records for
  processing, and what the Processing tab shows meanwhile.
- **Options:** (a) flat per-parameter actuals in v0 (one actual value per
  processing parameter, no step association) — captures something early, but
  the shape is throwaway: it loses the step context the owner wants, and
  would be migrated/replaced when the execution log lands; (b) **no**
  processing actuals in v0 — the Processing tab shows the planned processing
  parameters (from the snapshot) read-only as a reference, and actual
  processing values land together with the future step-by-step execution log.
- **Recommended resolution:** (b) — ingredient amounts, yield and
  observations already give v0 its traceability; recording processing values
  in a shape we know we will replace buys little. The planned snapshot (Q1)
  preserves the planned values so the future execution log has its base.
- **Answer**: Option (b) seems okay. Although I think the processing log is
  important, implementing it now can be too complicated.
- **Resolution:** option (b) — **no** processing actuals in v0. The Processing
  tab shows the planned processing parameters (from the Q1 snapshot) read-only
  as a reference; actual processing values land together with the future
  step-by-step execution log. The execution log is recorded as a later phase:
  the owner considers it important but too complicated to implement now
  (decision log 2026-09-03).

## 10. Decision Log

*Record answers and design decisions with dates. Keeps the letter as the
source of truth as it evolves.*

| Date | Decision | By |
|---|---|---|
| 2026-09-03 | Letter restructured to the Ingredients/Formulas template (§1–§10) from the owner's three-point draft; draft intent preserved verbatim (§1); Q1–Q7 raised for discussion | ducphu |
| 2026-09-03 | Q1: batch ↔ formula — `formula_id` + pinned `formula_version` + planned snapshot stored in the batch; formula edits never rewrite batch history | ducphu |
| 2026-09-03 | Q2: v0 actuals = one actual amount per ingredient (weighing happens up front) + actual yield + observations; processing values deferred as a step-by-step execution log (owner wants that shape; not v0) — see Q8 | ducphu |
| 2026-09-03 | Q3: the batch's plan = formula composition scaled to a user-set target yield (stored in the snapshot); same-unit guard applies, mixed units → manual plan rows; printing the scaled plan for weighing deferred ("come back later") | ducphu |
| 2026-09-03 | Q4: auto-generated read-only `batch_code` `B-####` + required free-text `name` | ducphu |
| 2026-09-03 | Q5: status selectbox planned \| in progress \| completed, default *planned*, no workflow | ducphu |
| 2026-09-03 | Q6: delete allowed only while *planned* and no linked samples/test reports; no duplicate action in v0 | ducphu |
| 2026-09-03 | Q7: detail navigation — hidden child page + `st.switch_page`, `?batch_id=` query param (Formulas precedent) | ducphu |
| 2026-09-03 | Q1 follow-up: batch stores `formula_id` + `formula_name` + `formula_version`, all pinned at creation and immutable — id for links/reverse queries, name + version as the display/history snapshot (`formula_name` added to §5.1) | ducphu |
| 2026-09-03 | Q8: processing actuals — none in v0 (option b); Processing tab shows planned values read-only; step-by-step execution log recorded as a later phase (owner: important, but too complicated to implement now) | ducphu |
| 2026-09-03 | Formulas reverse links landed (deferred item, formulas letter §6): `list_batches_by_formula` + `count_batches_by_formula_id` in the batches store/gateway (light summary rows, one GROUP BY for the overview); Formulas overview/detail show real batch counts and link into batch detail; Formulas' delete guard (that letter's Q12) blocks deleting a formula that batches reference — checked in the Formulas delete dialog via the batches service | ducphu |
| 2026-09-09 | Batches v0 marked implemented: this README's header said "implementation not started" though the module landed 2026-09-03 (service, gateway, pages, ~78 tests); header updated to reflect the real state | ducphu |
| 2026-09-09 | Actual-values bug fix (approved): the Composition editor's hidden identity columns (`ingredient_id`/`ingredient_name`) now genuinely ride in the editor data (`st.data_editor` `column_order` hides them from display), so saving actual amounts no longer stores `None` ids and no longer fails backend validation; detail save handlers surface validation problems | ducphu |
| 2026-09-09 | Save feedback is a small modal result dialog (`save_result_dialog`, shown at the end of the page run from session state): success ✓ / failure ✗ with the validation problems; dismissible (X / ESC / click-outside) or via OK, both clear the pending outcome. Replaces corner toasts — the Streamlit 1.60 frontend closes a toast when its element unmounts, and every save is followed by a rerun/`switch_page` (to refresh the editor + deviations or close the dialog), so toasts were closed before they could be seen — and replaces inline banners (they scroll away / vanish on rerun). Create/edit/delete dialog outcomes route through the same dialog | ducphu |
| 2026-09-09 | Reverse-link summaries now carry the pinned `formula_version` (`list_batches_by_formula` SELECT + gateway batch-summary contract extended): the Formulas detail Overview tab's "Batches from this formula" table shows a Version column per batch and the open-batch selectbox labels include it, so batches made from an older formula revision stand out once the formula has moved on (§6 bullet updated to match) | ducphu |
