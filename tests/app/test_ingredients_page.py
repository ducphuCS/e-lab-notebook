"""AppTest behavior tests for the Ingredients page.

Layer: app behavior (docs/TEST_STRATEGIES.md §4.4) — the page runs
headlessly via streamlit.testing.v1.AppTest; no browser, no network.

Each test points the page at its own temp SQLite file (via
monkeypatching store.DEV_DB_PATH), so tests never touch the dev database
and stay isolated from each other.
"""
import pytest
from streamlit.testing.v1 import AppTest

from backend.gateway import formulas as fgw
from backend.gateway import ingredients as gw


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Temp dev-DB path for the page under test.

    The page also reads the Formulas service for the reverse-link count
    (README §6), so that path is patched too — tests stay hermetic.
    """
    path = tmp_path / "ingredients.db"
    monkeypatch.setattr("backend.services.ingredients.store.DEV_DB_PATH", path)
    monkeypatch.setattr(
        "backend.services.formulas.store.DEV_DB_PATH",
        tmp_path / "formulas.db",
    )
    return path


def _page() -> AppTest:
    return AppTest.from_file("frontend/ingredients/app.py")


def _buttons(at: AppTest, label: str):
    return [b for b in at.button if b.label == label]


def test_page_loads_without_error(db_path) -> None:
    at = _page()
    at.run()
    assert not at.exception
    assert at.title[0].value == "Ingredients"
    assert any("No ingredients yet" in i.value for i in at.info)


def test_create_ingredient_flow(db_path) -> None:
    at = _page()
    at.run()
    _buttons(at, "➕ Add ingredient")[0].click()
    at.run()
    assert not at.exception

    at.text_input[0].set_value("Water")  # "Name *"
    at.selectbox[0].select("liquid")     # "State"
    _buttons(at, "Save")[0].click()
    at.run()

    assert not at.exception
    assert any(t.value == "Ingredient created." for t in at.toast)

    # persisted to the temp DB, listed on the page
    conn = gw.connect(db_path)
    try:
        assert [r["name"] for r in gw.list_ingredients(conn)] == ["Water"]
    finally:
        conn.close()
    assert len(at.dataframe) == 1


def test_create_rejects_missing_name(db_path) -> None:
    at = _page()
    at.run()
    _buttons(at, "➕ Add ingredient")[0].click()
    at.run()
    _buttons(at, "Save")[0].click()
    at.run()

    assert not at.exception
    errors = [e.value for e in at.error]
    assert any("Could not save ingredient" in e for e in errors)
    assert any("name" in e for e in errors)

    conn = gw.connect(db_path)
    try:
        assert gw.list_ingredients(conn) == []
    finally:
        conn.close()


def test_selecting_row_updates_details_in_same_run(db_path) -> None:
    """A table click refreshes the Details panel on the very rerun.

    Regression for the 2026-09-07 bug report: after the Details panel
    moved to the left column it is drawn before the table, so the panel
    only caught up on a *later* interaction. The selection is now read
    from the table's session state before the panel is drawn.
    """
    conn = gw.connect(db_path)
    try:
        gw.create_ingredient(conn, {"name": "Water", "state": "liquid"})
    finally:
        conn.close()

    at = _page()
    at.run()
    assert not any(m.value.startswith("### Water") for m in at.markdown)

    # A user click delivers the table's selection through session state
    # before the rerun starts.
    at.session_state["ingredients_table"] = {"selection": {"rows": [0]}}
    at.run()

    assert not at.exception
    assert any(m.value.startswith("### Water") for m in at.markdown)
    assert at.session_state["ingredients_selected_id"] is not None

def test_details_edit_and_delete_flow(db_path) -> None:
    # seed one ingredient in the temp DB
    conn = gw.connect(db_path)
    try:
        record = gw.create_ingredient(conn, {"name": "Water", "state": "liquid"})
    finally:
        conn.close()

    # details panel (selection pre-set — AppTest cannot drive row selection)
    at = _page()
    at.session_state["ingredients_selected_id"] = record["id"]
    at.run()
    assert not at.exception
    assert any(m.value.startswith("### Water") for m in at.markdown)
    assert any(m.label == "State" and m.value == "liquid" for m in at.metric)

    # edit flow
    _buttons(at, "✏️ Edit")[0].click()
    at.run()
    assert any("Edit ingredient" in m.value for m in at.markdown)
    at.text_input[0].set_value("Water (edited)")
    _buttons(at, "Save")[0].click()
    at.run()
    assert not at.exception
    assert any(t.value == "Ingredient updated." for t in at.toast)

    # delete flow (fresh page instance, same temp DB)
    at2 = _page()
    at2.session_state["ingredients_selected_id"] = record["id"]
    at2.run()
    _buttons(at2, "🗑️ Delete")[0].click()
    at2.run()
    assert any("cannot be undone" in w.value for w in at2.warning)
    _buttons(at2, "Confirm delete")[0].click()
    at2.run()

    assert not at2.exception
    conn = gw.connect(db_path)
    try:
        assert gw.list_ingredients(conn) == []
    finally:
        conn.close()


def _seed_formula_using(db_path, ingredient_id: int) -> None:
    """A formula whose live composition references the ingredient."""
    conn = fgw.connect(db_path.parent / "formulas.db")
    try:
        fgw.create_formula(
            conn,
            {
                "name": "Emulsion X",
                "status": "draft",
                "composition": [
                    {
                        "no": 1,
                        "ingredient_id": ingredient_id,
                        "ingredient_name": "Water",
                        "role": "solvent",
                        "amount": 90.0,
                        "uom": "g",
                        "notes": None,
                    }
                ],
            },
        )
    finally:
        conn.close()


def test_details_shows_formula_usage_count(db_path) -> None:
    conn = gw.connect(db_path)
    try:
        record = gw.create_ingredient(conn, {"name": "Water"})
    finally:
        conn.close()
    _seed_formula_using(db_path, record["id"])

    at = _page()
    at.session_state["ingredients_selected_id"] = record["id"]
    at.run()

    assert not at.exception
    metric = [
        m for m in at.metric if m.label == "Formulas using this ingredient"
    ]
    assert metric and str(metric[0].value) == "1"


def test_delete_blocked_while_a_formula_uses_the_ingredient(db_path) -> None:
    conn = gw.connect(db_path)
    try:
        record = gw.create_ingredient(conn, {"name": "Water"})
    finally:
        conn.close()
    _seed_formula_using(db_path, record["id"])

    at = _page()
    at.session_state["ingredients_selected_id"] = record["id"]
    at.run()
    _buttons(at, "🗑️ Delete")[0].click()
    at.run()

    assert not at.exception
    assert any("cannot be deleted" in w.value for w in at.warning)
    assert not _buttons(at, "Confirm delete")
    # the ingredient survives the blocked attempt
    conn = gw.connect(db_path)
    try:
        assert len(gw.list_ingredients(conn)) == 1
    finally:
        conn.close()
