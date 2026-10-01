# Test Reports — Intention Letter

> **Section:** Lab · **Status:** resolved + implemented 2026-10-01 —
> Q1–Q16 answered (§9); v0 shipped (service, gateway, overview + hidden
> detail pages, tests, and the Samples/Batches reverse links). Condensed from
> the owner's seven-point draft.

## 1. Intention

Test Reports records the **results of sample evaluations** — sensory,
shelf-life, stability, microbiology — closing the chain *formula → batch →
sample → report*. A report is one evaluation event covering **one or many
samples**; each sample's outcome is a **result row**, so report↔sample is
many-to-many via results. Report templates and their future analytics belong
to **Library → Test Methods**; v0 uses a single generic template and a
free-text method reference.

## 2. Scope

**In scope**

- Overview + hidden detail page.
- Report header (evaluation metadata) plus result rows, one per sample.
- Results as a structured table: `value` + `unit`.
- Template/Test Methods link seam (one template in v0).
- Reverse links from Samples (per-sample count, detail tab, delete guard) and
  from Batches (report count over the batch's samples).

**Out of scope (for now)**

- Analysis, charts, per-template rendering.
- Template authoring (Test Methods).
- Attachments (Documents).
- Equipment / Test Panels / Test Methods masters — free text / later links.
- Permissions, imports/exports (e.g. QL One).

## 3. User flows

- See all reports (method, evaluation date, person-in-charge).
- Create a report and record the evaluation metadata.
- Add a structured result row per evaluated sample.
- Open a report and read its header and results.
- Open a sample and see its reports/results.
- Edit or delete a report (delete cascades its results).

## 4. Layout

One **Lab** entry: overview + hidden `test_reports/detail.py` (`?report_id=`).

- **Overview** — read-only table: id, method, evaluation date,
  person-in-charge, sample count. Filters: method, date.
- **Detail** — header + tabs:
  - **Overview** — method, date, person-in-charge, methodology,
    equipment/panel, notes.
  - **Results** — one row per sample: sample link, transfer, parameter,
    value, unit, notes; add/edit/remove here.
  - *(Analysis — reserved; not rendered in v0.)*

## 5. Data

### 5.1 Schema

**Test report** (the evaluation event)

| Field | Req | Notes |
|---|---|---|
| id | yes | Internal PK. |
| test_method | yes | Free text in v0 (single generic template); becomes `test_method_id` when Test Methods lands. |
| evaluation_date | yes | Date the evaluation happened; default today. |
| person_in_charge | no | Free text — no user model yet. |
| methodology | no | Free text; owned by the Test Method later. |
| equipment | no | Free text; Equipment link later. |
| panel | no | Sensory panel; Test Panels link later. |
| notes | no | Free text. |
| created_at / updated_at | yes | ISO timestamps. |

**Test result** (one row per evaluated sample)

| Field | Req | Notes |
|---|---|---|
| id | yes | Internal PK. |
| report_id | yes | Parent report. |
| sample_id | yes | The evaluated sample. |
| transfer_id | yes | The transfer the result is anchored to; defaults to the sample's retention transfer. |
| parameter | yes | What was measured; template-defined later. |
| value | yes | Numeric result. |
| unit | no | Unit for `value` (e.g. cP, pH, %). |
| notes | no | Free text. |
| created_at / updated_at | yes | ISO timestamps. |

### 5.2 Derived-value rule

- Report **sample count** and per-sample **report/result count** are derived,
  never stored.
- Nothing analytical is computed or stored in v0.

### 5.3 Persistence

SQLite mockup via stdlib `sqlite3` + pandas, in
`backend/services/test_reports/`; dev DB at
`backend/services/test_reports/data/test_reports.db` (gitignored `*.db`).
Tests use temp/in-memory DBs; the gateway validates requests/responses
(`docs/TEST_STRATEGIES.md`).

## 6. Dependencies on other modules

- **Samples** — required: every result references a `sample_id` + `transfer_id`
  (the retention row guarantees a transfer). Wires three Samples placeholders:
  the detail **Test reports** tab, the overview count, and the delete guard's
  test-report clause. A result also **pins its transfer against deletion**.
- **Test Methods** (Library) — the template master; v0 single template +
  free-text method, linked properly later.
- **Equipment / Test Panels / Documents** — deferred; free text or later links.
- **Batches** — the downstream count is wired in the same pass: the batch's
  test-report count is derived from its samples' results, replacing the
  Batches placeholder. **Formulas** waits — reachable through
  batches/samples; no direct count or guard yet.

## 7. UX / widget choices

- Read-only `st.dataframe` + `st.dialog` CRUD, mirroring the other modules.
- Hidden detail page (`?report_id=`); result rows managed in the Results tab.
- Sample selectbox (code + origin) and a transfer selectbox scoped to it.
- Validation in pure utils; save feedback via the shared `notify()` helper.

## 8. Testing

Mirrors the other modules (`docs/TEST_STRATEGIES.md`): backend
service/validation unit tests, frontend pure-utils tests, contract fixtures,
and `tests/app/test_test_reports_page.py` with a faked gateway (dialogs
covered at service/contract/utils layers). Extend the Samples suites for the
new reverse links.

## 9. Resolved questions (Q1–Q16)

| # | Topic | Decision |
|---|---|---|
| Q1 | Page shape | Overview + hidden `detail.py` (`?report_id=`); tabs Overview / Results; Analysis reserved, not rendered. |
| Q2 | Report identity | Internal `id` only in v0. |
| Q3 | Template source | **One generic template for all reports** (essential info only); multi-template / Test Methods later. |
| Q4 | Template storage | Free text now; becomes `test_method_id` when Test Methods lands. |
| Q5 | Result payload | Structured row: `parameter`, `value`, `unit`, `notes`. |
| Q6 | Results per sample | Many allowed (replicates/timepoints); no unique constraint. |
| Q7 | Transfer anchor | Required on every result; defaults to the retention transfer. |
| Q8 | Required header | `test_method` + `evaluation_date`; the rest optional. |
| Q9 | Template vs methodology | Free-text `methodology` in v0; the Test Method owns it later. |
| Q10 | Lifecycle | Editable and deletable (cascade results, confirm); no `status` yet — may add later. |
| Q11 | Transfer pinning | A transfer referenced by a result cannot be deleted. |
| Q12 | Person-in-charge | Free text (no user model yet). |
| Q13 | Reverse links | Wired in the same pass: Samples (count, tab, delete guard) and Batches (report count over its samples); Formulas waits. |
| Q14 | Batch/formula guards | None added. |
| Q15 | Create flow | Header first, then result rows in the detail tab. |
| Q16 | Template vocabulary | v0 single template; the named families (sensory, shelf-life, stability, microbiology, other) are the future Test Methods vocabulary. |

## 10. Decision Log

| Date | Decision | By |
|---|---|---|
| 2026-10-01 | Reports and results separated: a report is the evaluation event; results are one row per evaluated sample (many-to-many via results). | ducphu |
| 2026-10-01 | Template master belongs to **Library → Test Methods**; v0 uses one generic template and a free-text method reference that later becomes `test_method_id`. | ducphu |
| 2026-10-01 | Results are structured (`parameter` / `value` / `unit`); analysis and per-template charts deferred. | ducphu |
| 2026-10-01 | Letter condensed from the seven-point draft; Q1–Q16 resolved. | ducphu |
| 2026-10-01 | Reverse links expanded: Batches' test-report count is wired in the same pass (over its samples); Formulas deferred. | ducphu |
| 2026-10-01 | Test Reports v0 implemented: SQLite service + gateway, overview + hidden detail page (`?report_id=`, tabs Overview / Results), dialog CRUD, tests. Reverse links wired: Samples (report count, Test reports tab, delete guard, transfer pinning) and Batches (distinct report count over its samples); Formulas deferred | ducphu |
