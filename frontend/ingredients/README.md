# Ingredients — Intention Letter

> **Template note:** this file is both the intention letter for the
> **Ingredients** page and the template to copy for other pages. Keep the
> section structure, replace the `<placeholders>` and the content. *Italicized
> lines are instructions — delete them when copying to a new page.*

> **Section:** Library · **Status:** resolved 2026-08-24 — all questions in §9
> answered; decisions recorded in §10. **Implemented** 2026-08-24 (Steps 1–6):
> backend service, gateway client, page, tests, `.gitignore`.

## 1. Intention

*One short paragraph: what this page does for the user, and why it matters.*

Show the list of all ingredients and let the user create, read, update, and
delete them (CRUD). The page is the source of truth for ingredient master data
(preferred names, suppliers) that other pages reference — DOE formulations
already use `item_code` / `item_description`.

## 2. Scope

*Bullet lists: what's in, what's explicitly out for now.*

**In scope**

- CRUD on ingredients.
- Two-column layout: details of the selected ingredient on the **left**
  (narrow panel), list on the **right** (wide).
- Placeholder state in the details panel when nothing is selected.
- Per-ingredient custom fields (free key/value pairs, user-defined names).

**Out of scope (for now)**

- Import/export (CSV upload/download).
- Attachments (SDS/COA) — Documents page owns attachments.
- Approval workflow for ingredient data changes.
- Sync/import from the external item-code system (fields filled manually).

## 3. User flows

*Short bullets: "As a user I can …".*

- As a user I can see the full list of ingredients.
- As a user I can select an ingredient and see its details (and related info).
- As a user I can create a new ingredient.
- As a user I can edit an existing ingredient.
- As a user I can delete an ingredient.

## 4. Layout

*Describe the page layout: columns, panels, and empty/placeholder states.*

Two columns (layout updated 2026-09-07 — the details panel now sits on the
left, the list stays wide on the right):

- **Left column (narrow)** — details and related information of the selected
  ingredient:
  - attributes grouped in rows to avoid scrolling: item code + item
    description (2 cols), supplier + UOM + state (3 cols), notes on its own
    row,
  - number of formulas using this ingredient (metric),
  - custom fields (editable key/value/unit rows),
  - add/edit form and delete button.
  When nothing is selected, show a placeholder ("Select an ingredient…").
- **Right column (wide)** — the full list of ingredients (read-only table;
  grows to show all rows). Selecting a row populates the left column.

## 5. Data

### 5.1 Schema (v0 — resolved 2026-08-24, see Q1)

| Field | Type | Required | Notes |
|---|---|---|---|
| id | integer | yes | Primary key, internal (auto-generated). `item_code` can't be the key — the external system owns it. |
| name | text | yes | Preferred display name for users. |
| item_code | text | no | From the external system; absent for new ingredients. Not unique. |
| item_description | text | no | From the external system; long-form spec. |
| supplier | text | no | Supplier name. |
| notes | text | no | User free-text notes. Named `notes` (not `description`) to avoid confusion with `item_description`. |
| uom | text | no | Default unit. Can prefill DOE formulation UOM later. |
| state | text | no | Physical state: liquid / solid / powder / … (selectbox). |
| custom_fields | json | no | Per-ingredient mapping of user-defined name → {value, unit}. See Q4. |

### 5.2 Persistence (resolved — see Q2)

SQLite mockup via stdlib `sqlite3` + pandas (no SQLAlchemy). DB-access code
lives in `backend/services/ingredients/`; the dev DB file lives in the repo
(`backend/services/ingredients/data/ingredients.db`) and is gitignored via
`*.db` (root `.gitignore` edit approved 2026-08-24). Tests use temp/in-memory
DBs, never the dev DB.

## 6. Dependencies on other modules

*Cross-module references made explicit so gaps are visible.*

- **External item-code system:** source of `item_code` / `item_description`.
  No sync/import in v0 — fields are filled manually.
- **Formulas** (Library): count of formulas using this ingredient (details
  panel). Formulas is a stub — the count will be a placeholder until it lands.
  When Formulas lands, the ingredient master also gains a unit-cost field
  (cost per uom) so formulas can derive cost contributions (Formulas letter
  Q8; decision log 2026-08-26).
- **DOE** (Analyze): reads `item_code` / `item_description` — keep field
  naming consistent.

## 7. UX / widget choices

*Which Streamlit widgets/patterns are used, and why; note consistency with
existing pages.*

- CRUD UX (Q3): read-only table with row selection + explicit add/edit form
  and delete button (details panel). Selection state lives in `session_state`.
  This is a **deliberate divergence** from the DOE page's `st.data_editor`
  pattern, chosen because row selection and inline editing conflict in one
  widget.
- Validation logic extracted into plain functions, following the DOE
  `validators.py` pattern.
- Pages stay thin glue: widgets → gateway call → display (per
  `docs/TEST_STRATEGIES.md`).

## 8. Testing

*How this page is tested, consistent with the existing test layout.*

- **Unit — service:** SQLite store CRUD logic in `tests/unit/backend/`
  (temp/in-memory DB, no network).
- **Contracts:** gateway request/response validation against golden JSON
  fixtures with mocked transport (`tests/contracts/`).
- **App behavior:** `tests/app/test_ingredients_page.py` with the gateway
  **faked** at the boundary (mirrors `tests/app/test_doe_page.py`).

## 9. Questions & Resolutions

*Each question keeps its history: status, context, options, resolution.*

### Q1. Schema — is `name` distinct from `item_description` / `description`?

- **Status:** resolved 2026-08-24
- **Context:** proposed schema had name, item_description and description —
  possibly redundant.
- **Resolution:** `name` is the user's preferred display name; `item_code` /
  `item_description` come from an external system and may be absent for new
  ingredients. `description` renamed to `notes` (user free-text). Added
  internal `id` as primary key since `item_code` is external-owned and not
  unique.

### Q2. Where does ingredient data persist?

- **Status:** resolved 2026-08-24
- **Resolution:** SQLite mockup (stdlib `sqlite3` + pandas). DB-access code in
  `backend/services/ingredients/`; dev DB file in the repo, gitignored
  (`*.db`, root `.gitignore` edit approved 2026-08-24). Tests use
  temp/in-memory DBs, never the dev DB. Backend/real DB integration comes
  later.

### Q3. CRUD UX

- **Status:** resolved 2026-08-24
- **Resolution:** option (b) — read-only table with row selection + explicit
  add/edit form and delete button. See §7 for the deliberate divergence from
  the DOE pattern.

### Q4. Custom fields — how are they modelled?

- **Status:** resolved 2026-08-24
- **Context:** details panel mentions custom fields; implies a flexible schema.
- **Resolution:** option (c), scoped — **per-ingredient** free key/value pairs
  (user-defined names), stored as a JSON column in v0 (no filtering by custom
  fields yet). EAV table is the evolution path if global field definitions or
  per-field queries are ever needed.
  - **Extended 2026-09-07:** each entry gains an optional `unit`; the stored
    shape is now `{name: {value, unit}}`. Backend validation accepts **only**
    this shape on both writes and reads (request + gateway response
    validation) — legacy plain-string values are rejected at the seam. Stored
    rows in the dev DB were migrated once to the new shape; no dual-shape
    support remains in the code. Real-user DBs still holding the old shape
    are rewritten in place via a **temporary** in-app button (§11) — remove
    it once every user has migrated.

### Q5. Should ingredients carry a default `uom`?

- **Status:** resolved 2026-08-24
- **Resolution:** yes — add optional `uom` (default unit) and `state`
  (physical state, selectbox: liquid / solid / powder / …). `uom` can prefill
  DOE formulation UOM later.

### Q6. How should we approach contracts between frontend and backend?

- **Status:** resolved 2026-08-24
- **Context:** `docs/TEST_STRATEGIES.md` already decides the seam: pages never
  do HTTP; all service access goes through the gateway (`backend/gateway/`);
  transport HTTP + JSON; gateway validates requests/responses (contract
  enforcement); gateway is fakeable in tests. Remaining question was phasing.
- **Resolution:** build the **minimal seam now** — `backend/services/ingredients/`
  (real SQLite service) + thin gateway client; the page calls the gateway
  in-process for now (no HTTP yet), so the HTTP swap later stays inside the
  gateway. Service unit tests, contract tests with mocked transport, and
  AppTest with a faked gateway land with it.

## 10. Decision Log

*Record answers and design decisions with dates. Keeps the letter as the
source of truth as it evolves.*

| Date | Decision | By |
|---|---|---|
| 2026-08-24 | Q1: schema v0 — internal `id` PK; `name` required; external `item_code`/`item_description` optional & non-unique; `description` → `notes` | ducphu |
| 2026-08-24 | Q2: SQLite mockup; DB-access in `backend/services/ingredients/`; dev DB gitignored (`*.db` added to `.gitignore` this day) | ducphu |
| 2026-08-24 | Q3: CRUD UX — read-only table + row selection, explicit add/edit form + delete button | ducphu |
| 2026-08-24 | Q4: custom fields per-ingredient key/value, JSON column in v0; EAV as evolution path | ducphu |
| 2026-08-24 | Q5: add optional `uom` and `state` fields | ducphu |
| 2026-08-24 | Q6: minimal seam now — SQLite service + thin gateway; page calls gateway in-process | ducphu |
| 2026-08-26 | Planned: ingredient master gains a unit-cost field (cost per uom) when the Formulas module lands (Formulas letter Q8); not implemented yet | ducphu |
| 2026-09-07 | Layout: details panel moved to the narrow **left** column; the list stays wide on the right | ducphu |
| 2026-09-07 | Custom fields: entries gain `unit`; stored shape `{name: {value, unit}}`; validation accepts only this shape; legacy plain-string rows migrated in the dev DB | ducphu |
| 2026-09-07 | **TEMP:** in-app migration button added so real-user DBs still in the old custom-field shape can be rewritten in place — **remove after all users migrate** (§11) | ducphu |

## 11. Temporary migration — legacy custom fields (remove me)

> **REMOVE AFTER:** every real user database has been migrated. Tracked in
> the decision log 2026-09-07 row above.

**Background.** v0 stored custom fields as `{name: plain value}`. Commit
`9e1c865` (2026-09-07) changed the shape to `{name: {value, unit}}`, and
validation now rejects the old shape on **read** — so a DB that still
contains legacy rows fails to load entirely. The dev DB was migrated by
hand; real user DBs need this one-time in-place update.

**How it works.** The Ingredients page counts legacy rows on every load
(`gw.count_legacy_custom_field_rows`). While any exist, the strict list
read is skipped and a **temporary** banner offers the update button; the
button calls `gw.migrate_legacy_custom_fields`, which rewrites each
`{name: value}` row to `{name: {value, unit: ""}}` in place. Migration is
one-way and idempotent; rows already in the current shape are untouched.

**To remove (once all users have migrated):**

1. `frontend/ingredients/app.py` — drop the `legacy_rows` handling in the
   data section, the banner call + empty-list branch in the layout, and the
   `_render_legacy_migration_banner` helper.
2. `backend/gateway/ingredients.py` — drop `count_legacy_custom_field_rows`
   and `migrate_legacy_custom_fields`.
3. `backend/services/ingredients/store.py` — drop
   `_legacy_custom_field_rows`, `count_legacy_custom_field_rows`,
   `migrate_legacy_custom_fields` and the `migration` import.
4. Delete `backend/services/ingredients/migration.py`.
5. Delete the migration tests: the whole files
   `tests/unit/backend/test_ingredients_migration.py` and
   `tests/unit/gateway/test_ingredients_gateway.py`, plus the migration
   cases added to `tests/unit/backend/test_ingredients_store.py`
   (`test_count_legacy_custom_field_rows`,
   `test_migrate_legacy_custom_fields_is_idempotent`) and to
   `tests/app/test_ingredients_page.py`
   (`test_legacy_custom_fields_banner_migrates_db`).
6. Remove this section and its decision-log row.
