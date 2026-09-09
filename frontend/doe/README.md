# DOE — Intention Letter (legacy)

> **Section:** Analyze · **Status:** legacy — this page descends from the
> earliest prototype ("Formulator Plan Mode") and is due for a **total
> revision** of the page. Short letter by design: DOE predates the
> Ingredients/Formulas/Batches template (§1–§10) and does not follow it.
> Write the full intention letter when the revision is designed.

## 1. What DOE is today

DOE is the Analyze module's page (currently the only one, see
`frontend/app.py`). It is a free-form experiment-drafting page:

- **Record Intent & Notes** — free-text notes area.
- **Experiment Details** (toggle) — context, objectives, hypothesis, fixed
  factors, outcomes.
- **Levels of Factors** — `st.data_editor` rows (factor / level_1 / level_2),
  validated by `validate_levels_df`.
- **Formulations** — `st.data_editor` rows keyed on item_code /
  item_description / uom / m_0, validated by `validate_formulations_df`.

Pure validation lives in `frontend/doe/validators.py`
(`tests/unit/frontend/test_doe_validators.py`); page behavior is covered by
`tests/app/test_doe_page.py`. The page was named **Formulator Plan Mode** at
the start and renamed **DOE** on 2026-08-24 (commit 057b95e) when the
section-based router landed.

## 2. Why it is legacy

- It predates the module-letter template and the current UX patterns. Its
  `st.data_editor` grid is the pattern that Ingredients (README §7), and
  later Formulas and Batches, deliberately diverged from (read-only table +
  row selection + explicit actions/dialogs).
- The Analyze vision (docs/PROGRAM.md §4.4, docs/IDEAS.md #11) is about
  learning from chains of DoEs and designing the next ones on top of that
  learning — reviewer collaboration, attachments, DoE-to-DoE links, and links
  to real Formulas. The current page only records free-form intent and draft
  tables.
- Its roots go back to archive/PROJECT.md (v1), which describes the "Plan
  mode" this page grew out of.

## 3. Revision direction (not design)

The page (folder, validators, tests, and this README) is planned for a total
revision when the Analyze module is designed. Hooks already recorded in other
letters:

- Formulas letter §6: DOE drafts (item_code / item_description / uom / m_0)
  should eventually link to real Formulas (ingredient ids); keep naming
  consistent so the bridge stays cheap.
- The traceability chain formula → batch → sample → test report is the data
  Analyze learnings build on (Formulas/Batches letters).

Until the revision, keep changes to this page minimal and avoid extending the
grid-based pattern; prefer the read-only-table + dialog patterns of
Ingredients/Formulas.
