"""AppTest behavior tests for the Formulas page.

Layer: app behavior (docs/TEST_STRATEGIES.md §4.4) — the page runs
headlessly via streamlit.testing.v1.AppTest; no browser, no network.

Known limitation: streamlit 1.60's AppTest has no st.dialog support, so
create/edit/delete/duplicate *submission* cannot be driven from AppTest
(any click inside a dialog closes it in the test tree). Those flows are
covered by the gateway/service unit tests, contract tests and the
frontend utils unit tests instead. AppTest here covers page loads,
rendering, and dialog opening.
"""
import pytest
from streamlit.testing.v1 import AppTest

from backend.gateway import formulas as gw


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Temp dev-DB paths for the page under test."""
    formulas_path = tmp_path / "formulas.db"
    monkeypatch.setattr("backend.services.formulas.store.DEV_DB_PATH", formulas_path)
    monkeypatch.setattr(
        "backend.services.ingredients.store.DEV_DB_PATH",
        tmp_path / "ingredients.db",
    )
    return formulas_path


def _page() -> AppTest:
    return AppTest.from_file("frontend/formulas/app.py")


def _buttons(at: AppTest, label: str):
    return [b for b in at.button if b.label == label]


def test_page_loads_without_error(db_path) -> None:
    at = _page()
    at.run()
    assert not at.exception
    assert at.title[0].value == "Formulas"
    assert any("No formulas yet" in i.value for i in at.info)


def test_add_formula_opens_dialog(db_path) -> None:
    """The create dialog renders (AppTest cannot submit it — see docstring)."""
    at = _page()
    at.run()
    _buttons(at, "➕ Add formula")[0].click()
    at.run()
    assert not at.exception
    assert any("New formula" in m.value for m in at.markdown)
    assert any(t.label == "Name *" for t in at.text_input)
    assert any(b.label == "Save" for b in at.button)
    # status selectbox defaults to the first enum value
    assert at.selectbox[0].value == "draft"


def test_overview_lists_seeded_formulas(db_path) -> None:
    conn = gw.connect(db_path)
    try:
        gw.create_formula(conn, {"name": "Emulsion X", "status": "draft"})
        gw.create_formula(conn, {"name": "Oil Base", "status": "active"})
    finally:
        conn.close()

    at = _page()
    at.run()
    assert not at.exception
    assert not any("No formulas yet" in i.value for i in at.info)
    assert len(at.dataframe) == 1  # the overview table
    df = at.dataframe[0].value
    assert set(df["name"]) == {"Emulsion X", "Oil Base"}
    assert set(df["status"]) == {"draft", "active"}
    assert list(df["batches"]) == [0, 0]  # placeholder stats


def test_stale_selection_after_delete_does_not_crash(db_path) -> None:
    """Deleting a selected row leaves the frontend holding the old row
    index; the overview must not index past the end of the smaller table
    (regression: 'single positional indexer is out-of-bounds')."""
    conn = gw.connect(db_path)
    try:
        first = gw.create_formula(conn, {"name": "Emulsion X", "status": "draft"})
        second = gw.create_formula(conn, {"name": "Oil Base", "status": "active"})
    finally:
        conn.close()

    at = _page()
    at.run()
    # user selects the second row (index 1) -> frontend stores rows=[1]
    from frontend.formulas.utils import FORMULAS_TABLE_KEY

    at.session_state[FORMULAS_TABLE_KEY] = {"selection": {"rows": [1]}}
    at.run()
    assert not at.exception
    assert any(b.label == "🗑️ Delete" for b in at.button)
    assert not any("Select a formula" in c.value for c in at.caption)

    # the second formula is deleted; the frontend echoes the STALE selection
    # (rows=[1]) on the rerun, like the real app after the delete dialog.
    conn = gw.connect(db_path)
    try:
        gw.delete_formula(conn, second["id"])
    finally:
        conn.close()
    at.session_state[FORMULAS_TABLE_KEY] = {"selection": {"rows": [1]}}
    at.run()
    assert not at.exception
    assert len(at.dataframe[0].value) == 1
    # out-of-bounds selection is ignored -> prompt to select, no buttons
    assert any("Select a formula" in c.value for c in at.caption)
    assert not any(b.label == "🗑️ Delete" for b in at.button)
    assert first["id"] in set(at.dataframe[0].value["id"])


def test_detail_page_loads_via_session_state(db_path) -> None:
    """Detail page with the formula id from session_state (AppTest cannot
    set query params)."""
    conn = gw.connect(db_path)
    try:
        record = gw.create_formula(conn, {"name": "Emulsion X", "status": "draft"})
    finally:
        conn.close()

    at = AppTest.from_file("frontend/formulas/detail.py")
    at.session_state["formulas_detail_id"] = record["id"]
    at.run()
    assert not at.exception
    assert at.title[0].value == "Emulsion X"
    assert any("Version: 1" in c.value for c in at.caption)
    # all six tabs render
    assert len(at.tabs) == 6
    # empty procedure -> empty state + add-step entry point
    assert any("No procedure defined" in i.value for i in at.info)
    assert any(b.label == "➕ Add step" for b in at.button)


def test_detail_procedure_panel_renders(db_path) -> None:
    """The Procedure panel renders steps, graph, details and actions.

    All tabs execute eagerly, so the Procedure panel's widgets are in the
    tree even though the Overview tab is the active one. Dialog submission
    is not drivable from AppTest (see module docstring); the step payload
    builder is covered by the utils tests.
    """
    conn = gw.connect(db_path)
    try:
        record = gw.create_formula(
            conn,
            {
                "name": "Emulsion X",
                "status": "draft",
                "composition": [
                    {
                        "no": 1,
                        "ingredient_id": 1,
                        "ingredient_name": "Water",
                        "role": "solvent",
                        "amount": 90.0,
                        "uom": "g",
                        "notes": None,
                    }
                ],
                "procedure": [
                    {
                        "name": "Mix",
                        "ingredients": [
                            {"ingredient_id": 1, "ingredient_name": "Water"}
                        ],
                        "equipment": "Blender",
                        "duration": "5 min",
                        "params": [
                            {"name": "speed", "value": "1000", "unit": "rpm"}
                        ],
                    }
                ],
            },
        )
    finally:
        conn.close()

    at = AppTest.from_file("frontend/formulas/detail.py")
    at.session_state["formulas_detail_id"] = record["id"]
    at.run()
    assert not at.exception
    # step list radio shows the step (AppTest reports formatted labels)
    assert any(r.options == ["1. Mix"] and r.value == 0 for r in at.radio)
    # step actions render
    assert any(b.label == "➕ Add" for b in at.button)
    assert any(b.label == "✏️ Edit" for b in at.button)
    assert any(b.label == "🗑️ Delete" for b in at.button)
    # subjects + processing params of the selected step render
    assert any("Subjects (ingredients)" in m.value for m in at.markdown)
    assert any("Processing parameters" in m.value for m in at.markdown)
    assert any("Water" in m.value for m in at.markdown)


def test_detail_page_missing_formula(db_path) -> None:
    at = AppTest.from_file("frontend/formulas/detail.py")
    at.session_state["formulas_detail_id"] = 999
    at.run()
    assert not at.exception
    assert any("no longer exists" in w.value for w in at.warning)


def test_detail_page_without_formula_id(db_path) -> None:
    at = AppTest.from_file("frontend/formulas/detail.py")
    at.run()
    assert not at.exception
    assert any("No formula selected" in i.value for i in at.info)
