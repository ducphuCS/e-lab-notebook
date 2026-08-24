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

## 2. What this project is

**ELN (Electronic Lab Notebook) v2** — a redesign of an R&D electronic lab
notebook for formulators, researchers, and the phys-chem lab. Product vision
and domain concepts live in `docs/PROGRAM.md`, `docs/IDEAS.md`, and
`archive/PROJECT.md`. Planned around four modules: **Overview, Library, Lab,
Analyze**.

## 3. Tech stack

- **Language:** Python (>=3.13; see `pyproject.toml`, `.python-version`)
- **Package manager:** `uv` (`uv.lock`, `.venv/` in repo root)
- **Dependencies:** `streamlit >= 1.60.0` (UI), `pandas >= 3.0.5` (data)
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

Target layout and current status:

| Path | Purpose | Status |
|---|---|---|
| `main.py` | Runs the app — launches the frontend (and backend) entrypoints. | exists, but only prints `Hello from eln-ver2!` — not yet functional |
| `frontend/app.py` | Frontend entrypoint (page router). | planned — not yet created |
| `frontend/<page>/` | One folder per page for modularization, each with its own files. Example: `frontend/formulator_plan_mode/app.py`. | pattern in use |
| `backend/app.py` | Backend entrypoint. | planned — not yet created |
| `backend/` | Backend modules. | empty |
| `tests/` | Tests. | empty |
| `docs/` | Product documentation (`PROGRAM.md`, `IDEAS.md`, `prompts/`). | committed |
| `archive/` | Older docs (e.g. `PROJECT.md`). | committed |
| `.env` | Empty env file. | — |

## 6. Current state

Early prototype. The last commit is `Update project docs`. Section 5's
architecture rule is the **target**; the codebase is still catching up:

- `main.py` does not run the app yet — it only prints `Hello from eln-ver2!`.
- `frontend/app.py` and `backend/app.py` do not exist yet.
- `frontend/formulator_plan_mode/app.py` is the only real code — a standalone
  Streamlit page, not yet routed through a frontend entrypoint.
- `frontend/sidebar/` and `frontend/project_page/` are empty leftover dirs
  from an earlier refactor. `project_page/` matches the page-folder pattern;
  `sidebar/` does not — decide its fate (keep / repurpose / delete) before
  building on either.
- Architecture decisions belong to the owner. Propose changes, don't assume
  them.

## 7. How to run

Per the architecture rule, the app is run from the root entrypoint:

```bash
uv run python main.py
```

⚠️ Until `main.py` actually runs the app, preview the current page directly:

```bash
uv run streamlit run frontend/formulator_plan_mode/app.py
```

## 8. Notes for agents

- The collaboration rules (section 1) override convenience. When in doubt, ask.
- `.env` exists but is empty.
- Keep changes consistent with the declared stack: Streamlit + pandas,
  Python >=3.13, uv-managed.
