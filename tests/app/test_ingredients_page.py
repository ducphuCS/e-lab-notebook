"""AppTest behavior tests for the Ingredients page.

Layer: app behavior (docs/TEST_STRATEGIES.md §4.4) — the page runs
headlessly via streamlit.testing.v1.AppTest; no browser, no network.

Each test points the page at its own temp SQLite file (via
monkeypatching store.DEV_DB_PATH), so tests never touch the dev database
and stay isolated from each other.
"""
import pytest
from streamlit.testing.v1 import AppTest

from backend.gateway import ingredients as gw


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Temp dev-DB path for the page under test."""
    path = tmp_path / "ingredients.db"
    monkeypatch.setattr("backend.services.ingredients.store.DEV_DB_PATH", path)
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


def test_legacy_custom_fields_banner_migrates_db(db_path) -> None:
    """TEMP migration UI: legacy-format rows hide the list and show a
    banner; the update button rewrites the DB row in place and the
    ingredient loads afterwards. Delete with the migration
    (frontend/ingredients/README.md §11).
    """
    from backend.services.ingredients import store

    # Seed exactly what a pre-2026-09-07 DB contains: custom_fields stored
    # as {name: plain value}. The gateway refuses to write this shape, so
    # go through the (validation-free) store.
    conn = store.connect(db_path)
    try:
        store.create_ingredient(
            conn, {"name": "Water", "custom_fields": {"pH": "7"}}
        )
    finally:
        conn.close()

    at = _page()
    at.run()
    assert not at.exception
    # the list is hidden and the migration banner is offered instead
    assert len(at.dataframe) == 0
    assert any("legacy" in w.value.lower() for w in at.warning)

    _buttons(at, "Update legacy custom fields")[0].click()
    at.run()

    assert not at.exception
    assert not any("legacy" in w.value.lower() for w in at.warning)
    assert len(at.dataframe) == 1

    conn = gw.connect(db_path)
    try:
        assert gw.list_ingredients(conn)[0]["custom_fields"] == {
            "pH": {"value": "7", "unit": ""}
        }
    finally:
        conn.close()


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
