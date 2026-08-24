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

## 4. Project layout (current, committed state)

| Path | Purpose |
|---|---|
| `frontend/formulator_plan_mode/app.py` | App entry point — the only real code so far. A standalone Streamlit "Formulator Plan Mode" page (intent notes, experiment details with a factor-levels `data_editor`, formulations draft, save button). |
| `frontend/sidebar/`, `frontend/project_page/` | Empty leftover dirs from a refactor that was removed from the working tree. Do not build on them without asking. |
| `backend/` | Reserved — empty, no code yet. |
| `tests/` | Reserved — empty, no tests yet. |
| `docs/` | Product documentation (`PROGRAM.md`, `IDEAS.md`, `prompts/`). |
| `archive/` | Older docs (e.g. `PROJECT.md`). |
| `main.py` | Root entrypoint (currently prints `Hello from eln-ver2!`). |
| `.env` | Empty env file. |

## 5. Current state

Early prototype. The last commit is `Update project docs`. An earlier,
unapproved navigation refactor (`frontend/app.py`, `frontend/pages/`,
`frontend/sidebar/` using `st.navigation`) was removed from the working tree;
only empty dirs remain. The app architecture is **open for discussion** —
propose changes, don't assume them.

## 6. How to run

```bash
uv run streamlit run frontend/formulator_plan_mode/app.py
```

## 7. Notes for agents

- The collaboration rules (section 1) override convenience. When in doubt, ask.
- `.env` exists but is empty.
- Keep changes consistent with the declared stack: Streamlit + pandas,
  Python >=3.13, uv-managed.
