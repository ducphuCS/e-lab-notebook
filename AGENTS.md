# AGENTS.md — ELN v2

> **Ownership:** This file belongs to the project owner (ducphu). It is
> auto-loaded into every agent session. Agents must not edit it without
> explicit approval.

## 1. Collaboration rules (non-negotiable)

1. **Code scope** — Implement code only inside `frontend/`, `backend/`, and
   `tests/`.
2. **Ask first, then wait** — Any modification outside those three folders —
   `AGENTS.md`, `docs/`, `archive/`, `main.py`, `pyproject.toml`, `.env`, root
   configs, anything else — requires explicit approval before touching it.
3. **No out-of-repo writes** — Never write to `/tmp/` or anywhere outside the
   repo. Scratch files go in `tests/_scratch/` and are cleaned up afterwards.
4. **Plan before editing** — State what will change and where before editing.
   Architecture-level changes require presenting the plan and **waiting** for
   approval.
5. **No git history rewrites** — Never `rebase`, `amend`, or force-push in this
   repo.
6. **Report changes** — End each session with a `git status` / `git diff`
   summary so the owner can review everything that changed.
7. **Docs are the source of truth** — `docs/` and `archive/` define product and
   domain requirements. If a request conflicts with them, ask before
   implementing.
8. **Docs freshness at commit time** — Before presenting changes for commit,
   check whether any source-of-truth doc went stale: audit the range
   `git log <last commit touching docs/ archive/ AGENTS.md>..HEAD` plus
   uncommitted changes; for each commit in range, judge whether it invalidates
   statements in `AGENTS.md` (§5 layout table, §6 current state, §7 run
   instructions) or in `docs/` / `archive/` (architecture, pages, modules,
   commands). Flag stale statements and propose the concrete edit — do not
   edit without explicit approval (rule 2).

## 2. What this project is

**ELN (Electronic Lab Notebook) v2** — a redesign of an R&D electronic lab
notebook for formulators, researchers, and the phys-chem lab. Product vision
and domain concepts live in `docs/PROGRAM.md`, `docs/IDEAS.md`, and
`archive/PROJECT.md`. Planned around four modules: **Overview, Library, Lab,
Analyze**.

## 3. Tech stack

- **Language:** Python (>=3.13; see `pyproject.toml`, `.python-version`)
- **Package manager:** `uv` (`uv.lock`, `.venv/` in repo root)
- **Dependencies:** `streamlit >= 1.60.0` (UI), `pandas >= 3.0.5` (data),
  `graphviz >= 0.19` (formula-procedure flow charts)
- **Dev dependencies:** `pytest >= 9.1.1` (see `docs/TEST_STRATEGIES.md`)
- **No JavaScript/Node tooling** — no `package.json` or frontend build config.

## 4. Implementation principles

**Prefer built-ins over custom code.** Use what the framework and libraries
(Streamlit, pandas, the Python standard library) already provide before
writing custom implementations — for both features and UI.

- Don't handcraft a function or widget that a library already supports.
- Avoid custom CSS and heavy styling; use the default look and behavior
  unless a requirement explicitly needs more.
- Keep implementations as simple as possible for maintainability — the
  simplest solution that works is preferred.

## 5. Project layout

> **Architecture rule (owner):** Each page has its own folder for
> modularization. `frontend/` and `backend/` each have their own `app.py` as
> entrypoint. The `main.py` in the root folder is used to run the app.

Current layout:

| Path | Purpose | Current content |
|---|---|---|
| `main.py` | Runs the app — launches the backend entrypoint, then the frontend router. | functional |
| `frontend/app.py` | Frontend entrypoint — `st.navigation` router over the four sections **Overview, Library, Lab, Analyze**. | functional |
| `frontend/<module>/` | One folder per module/page, each with its own files **and a README intention letter**. `formulas/`, `batches/` and `samples/` add a hidden `detail.py` child page (ids via `?formula_id=` / `?batch_id=` / `?sample_id=`). | pattern in use |
| `backend/app.py` | Backend entrypoint. | exists — placeholder (starts no services) |
| `backend/gateway/` | Gateway clients — the only place allowed to do transport; in-process for v0. | `ingredients.py`, `formulas.py`, `batches.py`, `samples.py` |
| `backend/services/` | Services (SQLite store + validation per module). | `ingredients/`, `formulas/`, `batches/`, `samples/` |
| `tests/` | pytest suites per `docs/TEST_STRATEGIES.md` (`unit/`, `contracts/`, `app/`). | populated |
| `docs/` | Product + methodology docs. | `PROGRAM.md`, `IDEAS.md`, `TEST_STRATEGIES.md`, `prompts/` |
| `archive/` | Older docs. | `PROJECT.md` |
| `.env` | Empty env file. | — |

**Implemented frontend modules:** Ingredients, Formulas, Batches, Samples,
DOE (legacy — see §6). **Registered placeholder stubs:** dashboard, projects,
equipment, test methods, test panels, documents, test reports.

## 6. Current state

The app runs end to end: `uv run python main.py` launches the frontend router
with four sections — Overview (dashboard, projects), Library (ingredients,
equipment, test methods, test panels, formulas, documents), Lab (batches,
samples, test reports), Analyze (DOE).

- **Ingredients** (Library) — the first module built in the current pattern:
  CRUD page with details panel, per-ingredient custom fields, SQLite service
  + gateway, full test suite.
- **Formulas** (Library) — v0: overview + hidden detail page (tabs Overview,
  Composition, Params, Procedure, Documents, Versions), dialog CRUD,
  procedure panel, new version only on composition change, delete guard
  against linked batches.
- **Batches** (Lab) — v0: create-from-formula plan scaled to a target yield,
  planned-vs-actual recording, lifecycle planned → in progress → completed,
  hidden detail page, delete-only-while-planned guard that now also blocks a
  batch that produced samples. Reverse links to Formulas and Samples are
  live.
- **Samples** (Lab) — v0: batch-born or standalone benchmark samples, a
  unique 3-char code, lifecycle active → depleted → expired, transfer events
  (`retention` + dispatches to other teams), hidden detail page, delete guard
  blocked by dispatches (test-report check is a placeholder). Reverse link to
  Batches is live (batch Samples tab + delete guard).
- **DOE** (Analyze) — **legacy**: inherited from the original "Formulator
  Plan Mode" page and slated for a total revision (`frontend/doe/README.md`).
- Registered-but-stub pages: dashboard, projects, equipment, test methods,
  test panels, documents, test reports (§5).

Recorded as **open** in the module letters: the ingredient unit-cost field +
formula cost contribution (Formulas letter Q8). The "Formulas using this
ingredient" reverse count is **live** (Ingredients letter, 2026-09-10): the
Ingredients details panel shows the real count and blocks deleting an
ingredient that a formula references.

Samples records as **open**: test reports (attach to sample + transfer) and
multi-team permissions (Samples letter §2/§6).

**About this section:** it is a deliberately lean snapshot. The authoritative
current state is the code, `git log`, and the per-module README letters under
`frontend/<module>/`; keep this section in sync when it drifts (rule 8).

## 7. How to run

Run the app from the root entrypoint:

```bash
uv run python main.py
```

or launch the frontend router directly during development:

```bash
uv run streamlit run frontend/app.py
```

Run the tests (no network — see `docs/TEST_STRATEGIES.md`):

```bash
uv run pytest tests/
```

## 8. Notes for agents

- The collaboration rules (section 1) override convenience. When in doubt, ask.
- `.env` exists but is empty.
- Keep changes consistent with the declared stack: Streamlit + pandas,
  Python >=3.13, uv-managed.
