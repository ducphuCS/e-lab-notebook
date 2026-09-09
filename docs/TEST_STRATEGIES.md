# TEST_STRATEGIES.md — ELN v2 Testing Architecture

> **Role.** This document is the guideline for **how ELN v2 is tested** and
> **how test cases are written**: the layering, the seams, the rules, and the
> test pyramid a module ships with. It is deliberately **not a status
> report** — it does not track which modules, tests, or tooling exist right
> now. Per-module implementation state lives in each module's intention
> letter (`frontend/<module>/README.md`); what exists today is visible from
> the code and `git log` itself.
>
> Product and domain requirements live in `docs/PROGRAM.md` and
> `docs/IDEAS.md`; they are not repeated here. Where a §9 decision's original
> wording tied a tool to a milestone that did not happen, the row is
> annotated 2026-09-09 — the *decision* stands as direction, the *timing
> note* does not.

## 1. Why this document exists

Testing on this project is deliberate and layered: each layer is tested at
its natural seam — unit tests for logic, contract tests at the gateway, page
behavior through `streamlit.testing.v1`, and the owner reviews pixels by
eye. No test depends on a browser, a network, or the repo's dev databases.

The guideline applies to every module as it lands: a new module ships with
its tests in the same shape as the modules before it (§8), and a change to
an existing module extends that module's suites rather than starting new
patterns.

## 2. Principles

1. **Test the logic, not the pixels.** Unit tests cover domain logic and
   frontend utility functions. Visual design is reviewed by the owner by eye.
2. **Prefer built-ins.** Use what Streamlit, pandas, and the standard library
   already provide before adding test tooling (e.g.
   `streamlit.testing.v1` before any browser automation).
3. **No out-of-repo writes.** Tests never write to `/tmp/` or anywhere
   outside the repo. Scratch files go in `tests/_scratch/` and are cleaned up
   afterwards.
4. **The seam is the gateway.** The gateway between frontend and services is
   the only place that does transport, and it is the boundary at which
   contracts are pinned and tested.
5. **Pages stay thin.** Streamlit page files are glue (widgets → state →
   display). Logic is extracted into plain functions so it is testable
   without a UI runtime.
6. **Backend stays Streamlit-free.** Backend/gateway code never imports
   `streamlit`, so it is testable headlessly.

## 3. Architecture context: the seam

```
Streamlit pages (frontend/<module>/app.py, detail.py)
      │  pages stay thin glue; logic lives in pure functions
      │  (frontend/<module>/utils.py, validators.py — unit-tested)
      ▼
Gateway client (backend/gateway/)   ← the ONLY code that does transport
      │  1. route to the right service (config, not hardcoded URLs)
      │  2. validate requests before they leave (fail fast)
      │  3. validate responses on the way back (contract enforcement)
      │  4. map every service failure to one uniform error shape
      ▼
transport — v0: in-process call to backend/services/<module>/store.py
            later: HTTP + JSON to microservices, some outside this repo
      ▼
services — backend/services/<module>/ (v0, SQLite) | remote (later)
```

**Hard rule (confirmed by the owner 2026-08-24):** pages never do transport
or HTTP directly — all service access goes through the gateway. In v0 that
makes the whole page → gateway → service → SQLite path runnable headlessly
against temp databases (§4.4); once HTTP exists, the gateway is the one
boundary to fake or mock.

## 4. The test pyramid, mapped to ELN v2

| Layer | What is tested | How | Network? |
|---|---|---|---|
| 1. Unit — backend | Service domain logic: store CRUD and validation rules (incl. snapshot/versioning, scaling, delete guards) | pytest, temp/in-memory SQLite | No |
| 2. Unit — frontend | Pure utility functions extracted from pages (validators, payload builders, derived values) | pytest | No |
| 3. Contracts + gateway unit | Gateway validators vs golden JSON fixtures; gateway routing/error/policy logic | pytest, transport faked or in-memory | No |
| 4. App behavior | Page behavior via `streamlit.testing.v1.AppTest`: widgets, clicks, session state, rendered output — against the real in-process gateway + temp DBs | pytest + AppTest | No |
| 5. Integration | Real end-to-end flows against real/remote services | pytest, `@pytest.mark.integration`, skipped by default | Yes |

### 4.1 Unit — backend

The backend must be written testable: pure functions, no `streamlit`
imports, no hidden global state. Each module in `backend/services/` gets a
mirroring pair in `tests/unit/backend/`:

- `test_<module>_store.py` — store CRUD and queries (temp/in-memory DB),
- `test_<module>_validation.py` — validation rules (required fields,
  same-unit guard, custom-field shape, status/lifecycle rules).

Domain rules belong here — delete guards, version snapshots, plan scaling,
deviation rules — because they are the cheapest layer to test and the most
expensive to retrofit. The gateway's own policy logic (identity
immutability, plan freeze, guard propagation) is likewise unit-tested
headlessly in `tests/unit/gateway/` over an in-memory connection (§4.3).

### 4.2 Unit — frontend

Page files remain thin glue. Anything with logic (validation, conversion,
defaults, calculations) is extracted into plain functions — e.g. DOE's
dataframe validators (the first extraction ever: `frontend/doe/validators.py`),
Ingredients' custom-field utils, Formulas' percentage derivation and payload
builders, Batches' scaling and deviation helpers — and tested in
`tests/unit/frontend/`. Working rule: *if a page needs a conditional or a
computation, extract it — don't leave it inline.*

### 4.3 Contracts and gateway unit

This is the layer the owner asked for: a *gateway* that pins the contract on
our side of the boundary. With services possibly moving outside the repo, a
remote service can drift without warning; the gateway keeps the seam honest.

- Golden JSON fixtures per service live in
  `tests/contracts/fixtures/<service>/` (`valid_record*.json` and
  `malformed_*.json`).
- Contract tests assert: *given this service record, the gateway validator
  accepts it; given this malformed one, it rejects it with a clear error.*
- The response validators are pure functions, so no network is involved; the
  one end-to-end check fakes the store (monkeypatch).
- Gateway-level logic that touches the store (routing, uniform error shape,
  policy guards) is unit-tested in `tests/unit/gateway/` over an in-memory
  connection.
- When the transport becomes HTTP, mock it (e.g. `httpx.MockTransport`);
  this layer still never touches the network.

### 4.4 App behavior — AppTest

Streamlit ships `streamlit.testing.v1.AppTest`, which runs a page in-process
and lets tests set widget values, click buttons, and assert on session state
and rendered elements. Because the v0 transport is in-process, AppTest runs
the **real** page → gateway → service stack: each test points every involved
service store at a temp SQLite file by monkeypatching `store.DEV_DB_PATH`
(and, when a page reads a second service — e.g. the Formulas page reads
Batches for reverse-link counts — that store's path too). No network, no dev
DB, hermetic and fast.

Automate, per page:

- **Smoke** — the page loads without error.
- **Navigation** — the router registers the right pages; detail navigation
  via query params works.
- **Behavior** — buttons/toggles do what they should (e.g. saving produces a
  valid record; selecting a row populates details).
- **Data integrity** — editors reject missing or invalid required input.

Caveat: streamlit 1.60's `testing.v1` has no `st.dialog` support, so dialog
*submission* flows (create/edit/delete/duplicate) are not drivable from
AppTest — they are covered by the service/gateway/contract/utils layers
instead. AppTest covers page loads, rendering, and dialog opening.

### 4.5 Integration — opt-in

A small, explicit set of end-to-end tests against real services, marked
`@pytest.mark.integration` and skipped by default. Only for flows the lower
layers cannot cover (e.g. a real round-trip through a service outside this
repo). Browser/Playwright automation, if ever needed, is reserved for a
minimal set of these flows and runs from within `tests/` — never `/tmp` or
the repo dev DBs.

## 5. UI/UX testing policy

- **During development:** the owner reviews UI/UX changes by eye and decides
  which way to go. Automated tests must not judge aesthetics or layout.
- **As the app grows:** automation covers *behavior* (smoke, navigation,
  widget behavior, data integrity — see §4.4), never visual design.
- **Not automated:** visual design, layout aesthetics, widget look-and-feel.
  Screenshot/visual-regression testing is considered overkill for an
  internal tool unless the owner decides otherwise.

## 6. Directory layout

```
tests/
├── conftest.py          # shared fixtures; the project is installed editable
│                        # (uv sync), so no sys.path manipulation is needed
├── _scratch/            # transient scratch space only (gitignored, never committed)
├── fixtures/            # shared data fixtures reflecting real domain data (add as needed)
├── unit/
│   ├── backend/         # unit tests mirroring backend/services/<module>/
│   ├── frontend/        # unit tests for pure utilities extracted from pages
│   └── gateway/         # gateway client logic (in-memory store / mocked transport)
├── contracts/           # gateway validators vs golden JSON fixtures
│   └── fixtures/<service>/   # valid_record*.json, malformed_*.json
├── app/                 # AppTest page-behavior tests (real gateway, temp DBs)
└── integration/         # opt-in end-to-end tests against real services (empty until needed)
```

Naming rule: because `tests/` is a flat (non-package) tree, **test file
names must be unique** across the whole tree (pytest imports by basename).
Follow the module convention: `test_<module>_store.py`,
`test_<module>_validation.py`, `test_<module>_utils.py`,
`test_<module>_page.py`, `test_<module>_gateway.py` /
`test_<module>_gateway_contract.py`.

## 7. Rules of the road

1. No writes outside the repo; scratch only in `tests/_scratch/`, cleaned up.
2. No `streamlit` imports in backend, gateway, or service code.
3. No transport/HTTP outside the gateway; pages call gateway functions only.
4. Page files stay thin; extract logic into tested utilities.
5. Keep test names unique across `tests/`.
6. Browser automation only as opt-in integration tests, from within `tests/`.

## 8. How a module ships its tests

The phasing below is the *recipe* every module follows, not a status log.
Order follows the dependency chain — the deeper, cheaper layers land first,
and the AppTest suite confirms the wiring last:

1. **Backend unit tests with the service** — store CRUD + validation rules
   in `tests/unit/backend/` (temp/in-memory DB). Domain rules (delete
   guards, version snapshots, scaling, schema shape) live here and are
   hardest to retrofit — write them as the service is written.
2. **Frontend unit tests as logic is extracted** — one test module in
   `tests/unit/frontend/` per pure util/validator.
3. **Contract + gateway tests with the gateway** — golden JSON fixtures per
   service in `tests/contracts/fixtures/<service>/` and gateway-level unit
   tests in `tests/unit/gateway/`.
4. **AppTest smoke + core flows** — the page in `tests/app/` with every
   involved store pointed at a temp DB. Dialog-submission flows that AppTest
   cannot drive stay covered by layers 1–3 (§4.4).

Origin: the first page predates this pattern — DOE (`frontend/doe/README.md`
marks it legacy). Ingredients was the first module to ship in this shape;
Formulas and Batches followed.

## 9. Decisions (approved by the owner on 2026-08-24; annotated 2026-09-09)

| # | Decision | Resolution (direction) | Today |
|---|---|---|---|
| 1 | Transport between gateway and services | **HTTP + JSON** once services are remote | v0 transport is in-process (gateway → SQLite store); no HTTP exists |
| 2 | Validation library | **pydantic** — the agreed approach if/when a remote or shared contract layer needs it | v0 validators are hand-written per service (`backend/services/<module>/validation.py`) + golden JSON fixtures; pydantic not introduced (the note that it would land "with the gateway" did not hold — the gateway landed without it) |
| 3 | `backend/` structure | **`backend/gateway/` + `backend/services/`** package folders (created 2026-08-24); `backend/app.py` was to keep its entrypoint role until the first real service landed | Services (ingredients, formulas, batches) have landed and are invoked in-process via gateways; `backend/app.py` is still a placeholder — how `main.py` wires real services is an open architecture question, not a testing one |
| 4 | Contract source of truth | **Golden JSON fixtures in this repo** (`tests/contracts/`); revisit a shared schema package only if multiple teams come to own services | In use for ingredients, formulas, batches |
| 5 | Hard rule: pages never do HTTP directly | **Confirmed** — all service access goes through the gateway | In effect (transport in-process) |
| 6 | Dev dependencies | **`pytest` added 2026-08-24** | `httpx` + `pydantic` were expected to land with the gateway but were not added; add them only when the remote transport/contract layer actually needs them (§9 rows 1–2), never speculatively |
| 7 | `tests/_scratch/` in `.gitignore` | **Added 2026-08-24** | In effect |

## 10. Running the tests

```bash
uv run pytest tests/                 # unit + contract + app tests (no network)
uv run pytest -m integration tests/  # only if real services are available
```

Per module or layer, run a subset, e.g. `uv run pytest tests/unit/backend/`
or `uv run pytest tests/app/test_batches_page.py`. `pytest` is a dev
dependency (added 2026-08-24).
