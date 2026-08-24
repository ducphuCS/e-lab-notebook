# TEST_STRATEGIES.md — ELN v2 Testing Architecture

> **Status:** approved by the owner (ducphu) on 2026-08-24; all decisions
> in §9 resolved the same day. This document is the source of truth for
> *how* ELN v2 is tested.
>
> Product and domain requirements live in `docs/PROGRAM.md` and
> `docs/IDEAS.md`; they are not repeated here.

---

## 1. Why this document exists

Testing was previously ad hoc — including browser-based checks that wrote
scratch files to `/tmp`, outside the repository. This document establishes a
deliberate, layered testing approach that:

- separates **backend** and **frontend** concerns,
- tests each layer at its natural seam,
- keeps the **owner in control of UI/UX decisions** during development,
- and scales as the backend becomes **microservices, some of which live
  outside this project**.

## 2. Principles

1. **Test the logic, not the pixels.** Unit tests cover domain logic and
   frontend utility functions. Visual design is reviewed by the owner by eye.
2. **Prefer built-ins.** Use what Streamlit, pandas, and the standard library
   already provide before adding test tooling (e.g. `streamlit.testing.v1`
   before any browser automation).
3. **No out-of-repo writes.** Tests never write to `/tmp/` or anywhere
   outside the repo. Scratch files go in `tests/_scratch/` and are cleaned up
   afterwards.
4. **The seam is the gateway.** The gateway between frontend and
   microservices is the only place that does HTTP, and it is the boundary at
   which contracts are validated and tested.
5. **Pages stay thin.** Streamlit page files are glue (widgets → state →
   display). Logic is extracted into plain functions so it is testable
   without a UI runtime.
6. **Backend stays Streamlit-free.** Backend/gateway code never imports
   `streamlit`, so it is testable headlessly.

## 3. Architecture context: the seam

```
Streamlit pages (frontend/)
      │  call page utility functions (pure, unit-tested)
      ▼
Gateway client (backend/gateway/)   ← the ONLY code allowed to do HTTP
      │  1. route to the right service (config, not hardcoded URLs)
      │  2. build + validate requests before they leave (fail fast)
      │  3. validate responses on the way back (contract enforcement)
      │  4. map every service failure to one uniform error shape
      ▼
HTTP + JSON
      │
      ▼
Microservices — some in backend/services/, some outside this repo
```

**Hard rule (confirmed by the owner 2026-08-24):** pages never touch HTTP
directly — all service access goes through the gateway. This is what makes
the gateway fakeable in tests and the contracts enforceable.

## 4. The test pyramid, mapped to ELN v2

| Layer | What is tested | How | Network? |
|---|---|---|---|
| 1. Unit — backend | In-repo microservice / domain logic, pure functions | pytest | No |
| 2. Unit — frontend | Pure utility functions extracted from pages (e.g. DataFrame validators, payload builders) | pytest | No |
| 3. Contracts — gateway validators | Request/response schemas against golden JSON fixtures; malformed service responses are rejected | pytest + mocked HTTP transport (`httpx.MockTransport`) | No |
| 4. App behavior | Page behavior via `streamlit.testing.v1.AppTest`: widget values, button clicks, session state, rendered output — with the gateway faked at the boundary | pytest + AppTest | No |
| 5. Integration | Real end-to-end flows against real services | pytest, `@pytest.mark.integration`, skipped by default | Yes |

### 4.1 Unit — backend domain logic

The backend must be written testable: pure functions, no `streamlit`
imports, no hidden global state. Each module in `backend/services/` gets a
mirroring test module in `tests/unit/backend/`.

### 4.2 Unit — frontend utilities

Page files remain thin glue. Anything with logic (validation, conversion,
defaults, calculations) is extracted into plain functions — e.g. a validator
for the `levels_df` / `formulations_df` shapes already edited in
`frontend/formulator_plan_mode/app.py` — and tested in
`tests/unit/frontend/`.

### 4.3 Contracts — the gateway validators

This is the layer the owner asked for: a *gateway* for communication between
frontend and backend. With microservices possibly outside the repo, a remote
service can drift without warning; the gateway pins the contract on our side.

- Golden JSON request/response fixtures per service live in
  `tests/contracts/`.
- Contract tests assert: *given this service response, the gateway accepts
  it; given this malformed one, it rejects it with a clear error.*
- The gateway validates requests **before** sending (fail fast, nice UI
  errors) and responses **on the way back** (contract enforcement).
- All HTTP is mocked in these tests — no network, deterministic, fast.

### 4.4 App behavior — AppTest

Streamlit ships `streamlit.testing.v1.AppTest`, which runs a page in-process
and lets tests set widget values, click buttons, and assert on session state
and rendered elements. No browser required.

Worth automating (as the app grows):

- **Smoke** — every page loads without error.
- **Navigation** — the page router registers the right pages; switching works.
- **Behavior** — toggles/buttons do what they should (e.g. Save produces a
  valid experiment object).
- **Data integrity** — editors reject missing required columns.

In these tests the gateway is **faked** (dependency injection at the page →
gateway call), so page behavior is tested without any network.

### 4.5 Integration — opt-in

A small, explicit set of end-to-end tests against real services, marked
`@pytest.mark.integration` and skipped by default. Only for flows that the
lower layers cannot cover (e.g. real round-trip through an external
service). Browser/Playwright automation, if ever needed, is reserved for a
minimal set of these flows and runs from within `tests/` — never `/tmp`.

## 5. UI/UX testing policy

- **During development:** the owner reviews UI/UX changes by eye and decides
  which way to go. Automated tests must not judge aesthetics or layout.
- **When the app grows:** automation covers *behavior* (smoke, navigation,
  widget behavior, data integrity — see §4.4), never visual design.
- **Not automated:** visual design, layout aesthetics, widget look-and-feel.
  Screenshot/visual-regression testing is considered overkill for an
  internal tool unless the owner decides otherwise.

## 6. Directory layout

```
tests/
├── conftest.py          # puts the repo root on sys.path; shared fixtures live here
├── _scratch/            # transient scratch space only (cleaned up, never committed content)
├── fixtures/            # shared data fixtures (CSV/JSON) reflecting real domain data
├── unit/
│   ├── backend/         # unit tests mirroring backend/services/ modules
│   ├── frontend/        # unit tests for pure utilities extracted from pages
│   └── gateway/         # unit tests for the gateway client (mocked transport)
├── contracts/           # gateway ↔ service contract tests + golden JSON payloads
├── app/                 # AppTest page-behavior tests (gateway faked)
└── integration/         # opt-in end-to-end tests against real services
```

Naming rule: because `tests/` is a flat (non-package) tree, **test file
names must be unique** across the whole tree (pytest imports by basename).

## 7. Rules of the road

1. No writes outside the repo; scratch only in `tests/_scratch/`, cleaned up.
2. No `streamlit` imports in backend or gateway code.
3. No HTTP outside the gateway; pages call gateway functions only.
4. Page files stay thin; extract logic into tested utilities.
5. Keep test names unique across `tests/`.
6. Browser automation only as opt-in integration tests, from within `tests/`.

## 8. Phasing

1. **Phase 1 (in progress, started 2026-08-24):** pytest scaffold; extract the first pure validators
   from `frontend/formulator_plan_mode/`; unit tests for them; one AppTest
   smoke test that the page loads.
2. **Phase 2 (as modules land):** backend microservice logic written
   alongside its unit tests; the gateway skeleton with one example service
   contract and its contract tests.
3. **Phase 3 (app is bigger):** per-module AppTest behavior suites;
   integration tests only where lower layers cannot cover the flow.

## 9. Decisions (all resolved by the owner on 2026-08-24)

| # | Decision | Resolution |
|---|---|---|
| 1 | Transport between gateway and services | **HTTP + JSON** |
| 2 | Validation library | **pydantic** — adopted when the gateway lands (Phase 2); Phase 1 validators stay stdlib/pandas-only |
| 3 | `backend/` structure | **`backend/gateway/` + `backend/services/`** package folders created 2026-08-24; `backend/app.py` keeps its entrypoint role until the first real service lands |
| 4 | Contract source of truth | **Golden JSON fixtures in this repo** (`tests/contracts/`); revisit a shared schema package only if multiple teams come to own services |
| 5 | Hard rule: pages never do HTTP directly | **Confirmed** — all service access goes through the gateway |
| 6 | Dev dependencies | **`pytest` added 2026-08-24** (pytest 9.1.1); `httpx` + `pydantic` land with the gateway (Phase 2) |
| 7 | `tests/_scratch/` in `.gitignore` | **Added 2026-08-24** |

## 10. Running the tests

```bash
uv run pytest tests/                 # unit + contract + app tests (no network)
uv run pytest -m integration tests/  # only if real services are available
```

`pytest` is a dev dependency (added 2026-08-24).
