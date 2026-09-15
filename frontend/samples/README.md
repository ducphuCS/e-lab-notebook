# Samples — Intention Letter

> **Section:** Lab · **Status:** resolved + implemented — Q1–Q15 answered
> by the owner (2026-09-15); decisions in §9–§10. Samples v0 implemented
> (service, gateway, overview + hidden detail pages, tests, plus the Batches
> reverse link + delete guard) — see the decision log for follow-ups.

## 1. Intention

Samples are the atomic unit of the Lab: the material taken from a batch, sent
to other teams, tested, compared and reported on. The traceability chain
*formula → batch → sample → test report* (PROGRAM.md §4, IDEAS.md #10) runs
through them — a sample carries the batch's identity everywhere it goes, and
test reports attach to the sample. Samples are what other R&D departments
(shelf-life, microbiology) mostly work on (archive/PROJECT.md).

The owner's draft, quoted as written:

> 1. Samples should come from a batche.
> 2. When a batch has samples, it can not be deleted.
> 3. A sample should have date of creation, which should be the same as the
>    batch it belongs to.
> 4. Sample should have an unique code, beside the default id. This code is
>    used when transfering sample between teams such as sending to shelf-life
>    or microbiology, which eventually results in the test reports later.
> 5. Users are allowed to set the sample as depleted or expired.
> 6. Samples should have a metric to tell how many weeks the samples are from
>    their creation.
> 7. I will want to discuss about the transfering of samples to other teams.
>    The first thought is that a sample can have a set of children samples
>    which are sent to other teams. The other thought is that we should create
>    a new sample from the same batches when sending to other teams. In this
>    case, the samples should have the information of this certain team. For
>    example, when sending to shelf-life, the sample should have information
>    about the storage condition, e.g., TA35, TA45, etc. The same is for
>    microbiology.
> 8. The idea above raises a different questions. Although the current
>    implementation is supporting mainly for formulators, we intend that other
>    departments in R&D will also use the application. For other teams, samples
>    are what they mostly work on. So how should we plan the page Sample?

## 2. Scope

**In scope**

- Overview of all samples with attributes and stats: origin, status, taken
  date, age in weeks, transfer count, test-report count (Q6, Q13).
- Detail page — one sample's story: origin, transfer history, test reports
  (Q9).
- Origin: a sample is **either batch-born** (batch link required) **or**
  standalone, e.g. a market benchmark (`origin` flag; Q1).
- Identity: internal id + unique 3-character code, suggested and confirmed by
  the user (Q3, Q11).
- Own creation date (`taken_at`), editable, independent of the batch (Q2).
- Status selectbox `active | depleted | expired`, default *active* (Q4).
- Transfers as **events, not copies** (Q6): each dispatch to shelf-life /
  microbiology records team, storage condition and date.
- One initial **`retention`** transfer per sample (in-house, no team,
  storage condition required) so a report always has a transfer to anchor to
  (Q7).
- Test reports linked to **sample + transfer**; upstream link through the
  batch to the formula (Q7).
- Delete policy: blocked by test reports or dispatches (Q8, Q12).

**Out of scope (for now)**

- Quantity / consumption tracking — *depleted* is a manual status (Q5).
- Child samples / aliquots (Q6).
- Derived *expired* (shelf-life rules) — user-set in v0 (Q4).
- "Current team / storage" display — a sample can be dispatched repeatedly,
  so the transfer history is the source of truth (Q13).
- Attachments (Documents owns them), import/export, label printing.
- Multi-team access control / permissions; a Library master for storage
  conditions (Q10, Q15).

## 3. User flows

- See all samples with attributes and stats (age, transfer count, reports).
- Create a sample from a batch, or record a standalone benchmark (Q1).
- Confirm or override the suggested sample code, and pick the storage
  condition for the initial retention transfer (Q7, Q11).
- Open a sample: origin, transfer history, related test reports.
- Set status (*active*, *depleted*, *expired*) (Q4).
- Add a dispatch transfer (team + storage condition) (Q6).
- Edit, and delete under the guard (Q8, Q12).

## 4. Layout

Two views over the single Lab sidebar entry (Formulas/Batches precedent, Q9):

- **Overview** — read-only table: sample code, origin (batch link or
  *benchmark*), status, taken date, age in weeks, transfer count,
  test-report count. Filters: status, batch. No "current team" column (Q13).
- **Detail** (hidden child page, `?sample_id=`) — header (code, origin,
  status) + tabs:
  - **Overview** — origin (batch → formula link, or benchmark `source`),
    taken date, status, notes.
  - **Transfers** — newest first: kind (`retention` / `dispatch`), team, sent
    date, storage condition, sent by, notes. The retention row is read-only;
    dispatches are added/edited here (Q6, Q7).
  - **Test reports** — reports for this sample (each anchored to a transfer)
    and their panels (placeholders until Test Reports lands, Q7).

Create / edit / delete launch from overview and detail; empty states per view.

## 5. Data

### 5.1 Schema (v0 — all fields resolved in §9)

**Sample**

| Field | Type | Required | Notes |
|---|---|---|---|
| id | integer | yes | Internal PK. |
| sample_code | text | yes | Unique 3-char code, suggested then confirmed/overridden (Q3, Q11). |
| origin | text | yes | `batch \| benchmark`. |
| batch_id | integer | conditional | Required iff `origin = batch`, null for benchmarks (Q1). |
| source | text | no | Supplier / brand, mainly benchmarks (Q14). |
| taken_at | text | yes | Sample's own date, default today, editable (Q2). |
| status | text | yes | `active \| depleted \| expired`, default *active* (Q4). |
| notes | text | no | Free text. |
| created_at / updated_at | text | yes | ISO timestamps. |

**Sample transfer**

| Field | Type | Required | Notes |
|---|---|---|---|
| id | integer | yes | Internal PK. |
| sample_id | integer | yes | Parent sample. |
| kind | text | yes | `retention \| dispatch`; exactly one retention row per sample. |
| to_team | text | conditional | Required for `dispatch`, null for `retention` (Q7). |
| sent_at | text | yes | Retention defaults to `taken_at`. |
| storage_condition | text | yes | Enum: refrigerator, room temperature, TA35, TA45 (Q15). |
| sent_by | text | no | Person who dispatched. |
| notes | text | no | Free text. |

Dropped from earlier proposals: `quantity`/`uom` (Q5), `parent_sample_id`
(Q6), and any sample-level `team`/`storage_condition` (Q6, Q13).

### 5.2 Derived-value rule

- **Weeks since creation** — derived from `taken_at`, never stored (Q2).
- **Transfer count** and **test-report count** — derived for the overview
  (Q6, Q13).
- **Expired** — user-set in v0; deriving it from shelf-life is a v1 candidate
  (Q4).
- **No "current team / storage"** — the transfer history is the source of
  truth (Q13).

### 5.3 Persistence

SQLite mockup via stdlib `sqlite3` + pandas (no SQLAlchemy), as in
Ingredients/Formulas/Batches. Code in `backend/services/samples/`; dev DB at
`backend/services/samples/data/samples.db` (covered by the existing `*.db`
gitignore rule). Tests use temp/in-memory DBs; service stays dumb, validation
shared, gateway validates requests/responses (`docs/TEST_STRATEGIES.md`).

## 6. Dependencies on other modules

- **Batches** — batch-born samples reference it; the Batches letter §6 defers
  the sample link here. Its delete guard (Q6) already blocks deleting a batch
  with linked samples, matching item 2. Benchmarks have no batch.
- **Formulas** — reachable through the batch; benchmarks have no formula
  lineage (Q1).
- **Test reports** — attach to **sample + transfer**; the retention row
  guarantees the transfer link is never null (Q7). Panel↔report link is Test
  Reports' letter to define.
- **Documents**, **other R&D teams** — attachments out of scope; teams are
  recorded on dispatches, no permissions in v0 (Q10).

## 7. UX / widget choices

- Read-only `st.dataframe` + `st.dialog` CRUD, mirroring
  Ingredients/Formulas/Batches.
- Create dialog: code suggestion (accept / another / own) + storage-condition
  selectbox for the retention transfer.
- Transfers tab: add/edit dispatches; retention row read-only and
  non-deletable.
- Hidden `samples/detail.py` + `?sample_id=` (Q9). Validation in pure utils;
  save feedback via the shared `frontend/common.py` `notify()` helper.

## 8. Testing

Mirrors the other modules (`docs/TEST_STRATEGIES.md`): service CRUD +
validation in `tests/unit/backend/` (origin rule, code uniqueness, transfer
rules, delete guard), pure utils in `tests/unit/frontend/` (age, counts),
contract fixtures in `tests/contracts/`, and `tests/app/test_samples_page.py`
with a faked gateway (dialogs covered at service/contract/utils layers, as
`st.dialog` is unsupported in streamlit 1.60 `testing.v1`).

## 9. Questions & Resolutions

*All resolved 2026-09-15. History kept compact: status, resolution, owner's
answer where it adds nuance.*

### Q1. Can a sample exist without a batch?

- **Status:** resolved 2026-09-15
- **Resolution:** option (c) — required `origin` flag (`batch | benchmark`);
  `batch_id` required iff batch-born. Permissions deferred (Q10).
- **Answer:** "…sometimes the samples can be benchmarks from market … If the
  samples are created from batches, they should have the batch_id, otherwise,
  a flag, e.g. benchmark, seems fine as well."

### Q2. Sample date and "weeks since creation"?

- **Status:** resolved 2026-09-15
- **Resolution:** option (a) — own `taken_at` (default today, editable),
  independent of the batch; age derived from it.
- **Answer:** "Sample can have its own creation date."

### Q3. Sample identity — code and generation?

- **Status:** resolved 2026-09-15
- **Resolution:** supersedes sequential `S-####`: a **3-character
  alphanumeric code** (e.g. `4A8`), randomly suggested at creation and
  confirmed or overridden by the user; batch-derived codes dropped.
- **Answer:** "R&D usually use a 3-letter sample code … generate that
  randomly as suggestions and the users will confirm or input their own."

### Q4. Status model?

- **Status:** resolved 2026-09-15
- **Resolution:** option (a) — one selectbox `active | depleted | expired`,
  default *active*, user-set, no workflow.
- **Answer:** "consistent with other pages."

### Q5. Quantity and *depleted*?

- **Status:** resolved 2026-09-15
- **Resolution:** option (a) — no quantity/uom in v0; *depleted* is manual;
  consumption tracking waits for warehouse management.
- **Answer:** "I don't think we need the quantity. Maybe later."

### Q6. Cross-team transfer — children, new samples, or records?

- **Status:** resolved 2026-09-15
- **Resolution:** option (c) — transfer events on one sample; no children /
  aliquots in v0.
- **Answer:** "Your idea about transfer records sound interesting. I will go
  with that first."

### Q7. Test report ↔ transfer link?

- **Status:** resolved 2026-09-15
- **Resolution:** option (c) — every sample gets one initial **`retention`**
  transfer (no `to_team`, required storage condition chosen at creation);
  reports link to **sample + transfer**, required; retention row read-only
  and non-deletable.
- **Answer:** "I think option (c) meaning one default transfer link seems
  okay."

### Q8. Delete policy?

- **Status:** resolved 2026-09-15
- **Resolution:** option (a) — deletion blocked while the sample has linked
  test reports (guard refined in Q12).
- **Answer:** "Option (a) aligns with what we have already done."

### Q9. Page shape?

- **Status:** resolved 2026-09-15
- **Resolution:** option (a) — overview + hidden `samples/detail.py`,
  `?sample_id=`, tabs Overview / Transfers / Test reports.
- **Answer:** "Hidden detail page seems okay."

### Q10. Multi-team scope?

- **Status:** resolved 2026-09-15
- **Resolution:** option (a) — record-only; teams on transfers; permissions
  deferred.
- **Answer:** "the scope of page Samples is about managing the samples …
  the transfer link is good enough for now."

### Q11. Sample code rules?

- **Status:** resolved 2026-09-15
- **Resolution:** exactly 3 chars, uppercase `A–Z0–9`, ambiguous characters
  excluded, unique case-insensitively, one regenerable suggestion, frozen
  after creation.
- **Answer:** "all the points seem fine. The ambiguous character exclusion
  seems fine too."

### Q12. Do transfers block deletion?

- **Status:** resolved 2026-09-15
- **Resolution:** option (a) with the retention row carved out — deletion
  blocked by test reports **or any `dispatch`**; the retention row never
  blocks.
- **Answer:** "we will have a default transfer record so (a) is fine."

### Q13. Current team / storage — derived or stored?

- **Status:** resolved 2026-09-15
- **Resolution:** neither — **no "current" concept**; the Transfers tab is
  the source of truth and the overview shows a transfer count.
- **Answer:** "since the sample can be transferred to teams many times,
  answering what was the latest one has no value. Users should check the
  transfer records themselves."

### Q14. Benchmark origin values and `source`?

- **Status:** resolved 2026-09-15
- **Resolution:** option (b) — `origin` stays `batch | benchmark`; an
  **optional** `source` column carries supplier / brand, mainly for
  benchmarks.
- **Answer:** "A separate optional column for source seems better."

### Q15. Storage-condition enum values?

- **Status:** resolved 2026-09-15
- **Resolution:** one general list for all teams, hardcoded in v0:
  **refrigerator, room temperature, TA35, TA45** (selectbox + validation;
  revisit if microbiology needs its own values). Applies to both retention
  and dispatch rows.
- **Answer:** "a general list with refregator, room temperature, TA35, TA45
  is fine for now."

## 10. Decision Log

| Date | Decision | By |
|---|---|---|
| 2026-09-15 | Letter restructured to the house template from the owner's eight-point draft (preserved verbatim in §1); Q1–Q15 resolved the same day | ducphu |
| 2026-09-15 | Q1: `origin` flag `batch \| benchmark`; `batch_id` required iff batch-born; permissions deferred | ducphu |
| 2026-09-15 | Q2: sample carries its own `taken_at`; age in weeks derived from it | ducphu |
| 2026-09-15 | Q3/Q11: 3-char uppercase code (`A–Z0–9`, ambiguous chars excluded), suggested and user-confirmed, unique case-insensitive, frozen after creation | ducphu |
| 2026-09-15 | Q4: status selectbox `active \| depleted \| expired`, default *active*, no workflow | ducphu |
| 2026-09-15 | Q5: no quantity/uom in v0; *depleted* manual | ducphu |
| 2026-09-15 | Q6: handoffs are transfer records (`sample_transfers`) on one sample; no child samples/aliquots in v0 | ducphu |
| 2026-09-15 | Q7: one initial `retention` transfer per sample (no team, required storage condition); reports link to sample + transfer, required; retention read-only | ducphu |
| 2026-09-15 | Q8/Q12: delete blocked by test reports or any `dispatch`; retention never blocks (the `kind` column exists for this) | ducphu |
| 2026-09-15 | Q9: overview + hidden detail page (`?sample_id=`) with Overview / Transfers / Test reports tabs | ducphu |
| 2026-09-15 | Q10: Samples records teams via transfers only; permissions / multi-team access deferred | ducphu |
| 2026-09-15 | Q13: no "current team/storage" value; transfer history is the source of truth, overview shows a transfer count | ducphu |
| 2026-09-15 | Q14: optional `source` column for supplier / brand provenance (mainly benchmarks) | ducphu |
| 2026-09-15 | Q15: storage-condition enum = refrigerator, room temperature, TA35, TA45 (general list, hardcoded in v0) | ducphu |
| 2026-09-15 | Samples v0 implemented: service (samples + sample_transfers, SQLite), gateway with the identity/retention/delete guards, overview + hidden detail page (`?sample_id=`, tabs Overview / Transfers / Test reports), dialog CRUD, and tests. Batches wired in the same pass: real samples count on its overview/detail, a Samples tab list linking into sample detail, and the delete guard blocking a batch that produced samples | ducphu |
| 2026-09-15 | Implementation decisions confirmed by the owner: ambiguous characters excluded from the code alphabet (`A–Z0–9` minus `O 0 I 1 L`); the overview counts **dispatches only** (the retention row is an anchor, not a hand-off); transfers carry no `created_at`/`updated_at` (the letter's schema); `sample_code`/`origin`/`batch_id` are frozen after creation; the page resolves `batch_code` from the Batches service (no denormalized snapshot); age in weeks = completed weeks | ducphu |
