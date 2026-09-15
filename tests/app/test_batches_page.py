"""AppTest behavior tests for the Batches page.

Layer: app behavior (docs/TEST_STRATEGIES.md §4.4) — the page runs
headlessly via streamlit.testing.v1.AppTest; no browser, no network.

Known limitation: streamlit 1.60's AppTest has no st.dialog support, so
create/edit/delete *submission* cannot be driven from AppTest (any click
inside a dialog closes it in the test tree). Those flows are covered by
the gateway/service unit tests, contract tests and the frontend utils
unit tests instead. AppTest here covers page loads, rendering, and dialog
opening.
"""
import pytest
from streamlit.testing.v1 import AppTest

from backend.gateway import batches as gw
from backend.gateway import samples as sgw
from frontend.batches import utils


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Temp dev-DB paths for the page under test (batches + formulas —
    the create dialog reads the Formulas service — and samples, which the
    detail Samples tab and delete guard read)."""
    batches_path = tmp_path / "batches.db"
    monkeypatch.setattr("backend.services.batches.store.DEV_DB_PATH", batches_path)
    monkeypatch.setattr(
        "backend.services.formulas.store.DEV_DB_PATH",
        tmp_path / "formulas.db",
    )
    monkeypatch.setattr(
        "backend.services.samples.store.DEV_DB_PATH",
        tmp_path / "samples.db",
    )
    return batches_path


def _formula() -> dict:
    """A formula record as the Formulas service would return it."""
    return {
        "id": 5,
        "name": "Emulsion X",
        "version": 3,
        "composition": [
            {
                "no": 1,
                "ingredient_id": 7,
                "ingredient_name": "Water",
                "role": "solvent",
                "amount": 90.0,
                "uom": "g",
                "notes": None,
            },
            {
                "no": 2,
                "ingredient_id": 8,
                "ingredient_name": "Oil",
                "role": "emollient",
                "amount": 10.0,
                "uom": "g",
                "notes": None,
            },
        ],
        "procedure": [],
    }


def _payload(name: str = "Emulsion 2500g", formula: dict | None = None) -> dict:
    formula = formula or _formula()
    return {
        "name": name,
        "formula_id": formula["id"],
        "formula_name": formula["name"],
        "formula_version": formula["version"],
        "status": "planned",
        "planned": utils.build_planned(formula, target_amount=2500.0, target_uom="g"),
        "actual": {},
    }


def _page() -> AppTest:
    return AppTest.from_file("frontend/batches/app.py")


def _buttons(at: AppTest, label: str):
    return [b for b in at.button if b.label == label]


def test_page_loads_without_error(db_path) -> None:
    at = _page()
    at.run()
    assert not at.exception
    assert at.title[0].value == "Batches"
    assert any("No batches yet" in i.value for i in at.info)


def test_add_batch_opens_dialog(db_path) -> None:
    """The create dialog renders (AppTest cannot submit it — docstring).
    With no formulas yet it explains there is nothing to batch from."""
    at = _page()
    at.run()
    _buttons(at, "➕ Add batch")[0].click()
    at.run()
    assert not at.exception
    assert any("New batch" in m.value for m in at.markdown)
    assert any(
        "No formulas yet" in w.value for w in at.warning
    )


def test_overview_lists_seeded_batches(db_path) -> None:
    conn = gw.connect(db_path)
    try:
        gw.create_batch(conn, _payload(name="First run"))
        second = gw.create_batch(conn, _payload(name="Second run"))
    finally:
        conn.close()

    at = _page()
    at.run()
    assert not at.exception
    assert not any("No batches yet" in i.value for i in at.info)
    assert len(at.dataframe) == 1  # the overview table
    df = at.dataframe[0].value
    assert set(df["code"]) == {"B-0001", "B-0002"}
    assert set(df["name"]) == {"First run", "Second run"}
    assert set(df["formula"]) == {"Emulsion X"}
    assert set(df["status"]) == {"planned"}
    assert list(df["samples"]) == [0, 0]  # placeholder stats
    # most recent batch first (lab-notebook order)
    assert df.iloc[0]["code"] == "B-0002"
    assert df.iloc[0]["id"] == second["id"]


def test_stale_selection_after_delete_does_not_crash(db_path) -> None:
    """Deleting a selected row leaves the frontend holding the old row
    index; the overview must not index past the end of the smaller table
    (regression guard mirroring Formulas)."""
    conn = gw.connect(db_path)
    try:
        gw.create_batch(conn, _payload(name="A"))
        second = gw.create_batch(conn, _payload(name="B"))
    finally:
        conn.close()

    at = _page()
    at.run()
    at.session_state[utils.BATCHES_TABLE_KEY] = {"selection": {"rows": [1]}}
    at.run()
    assert not at.exception
    assert any(b.label == "🗑️ Delete" for b in at.button)

    # the second batch is deleted behind the scenes; the frontend echoes the
    # STALE selection (rows=[1]) on the rerun, like after the delete dialog.
    conn = gw.connect(db_path)
    try:
        gw.delete_batch(conn, second["id"])
    finally:
        conn.close()
    at.session_state[utils.BATCHES_TABLE_KEY] = {"selection": {"rows": [1]}}
    at.run()
    assert not at.exception
    assert len(at.dataframe[0].value) == 1
    assert any("Select a batch" in c.value for c in at.caption)
    assert not any(b.label == "🗑️ Delete" for b in at.button)


def test_detail_page_loads_via_session_state(db_path) -> None:
    """Detail page with the batch id from session_state (AppTest cannot
    set query params)."""
    conn = gw.connect(db_path)
    try:
        record = gw.create_batch(conn, _payload())
    finally:
        conn.close()

    at = AppTest.from_file("frontend/batches/detail.py")
    at.session_state["batches_detail_id"] = record["id"]
    at.run()
    assert not at.exception
    assert at.title[0].value == "Emulsion 2500g"
    assert any("B-0001" in c.value for c in at.caption)
    assert any("made from Emulsion X v3" in c.value for c in at.caption)
    # all four tabs render
    assert len(at.tabs) == 4
    # composition editor + recording surfaces render (editor *contents* are
    # covered by the utils unit tests — AppTest in 1.60 has no data_editor)
    assert any(
        "Actual amounts per ingredient" in m.value for m in at.markdown
    )
    # no processing plan -> empty state; samples placeholders
    assert any("No processing plan" in i.value for i in at.info)
    assert any(m.label == "Samples" for m in at.metric)
    assert any(m.label == "Test reports" for m in at.metric)
    # run-details + actuals save surfaces render
    assert any(b.label == "Save run details" for b in at.button)
    assert any(b.label == "Save actual amounts" for b in at.button)


def test_detail_samples_tab_lists_samples(db_path) -> None:
    """The Samples tab now reads the real reverse link (README §6)."""
    conn = gw.connect(db_path)
    try:
        record = gw.create_batch(conn, _payload())
    finally:
        conn.close()

    sconn = sgw.connect(db_path.parent / "samples.db")
    try:
        sgw.create_sample(
            sconn,
            {
                "sample_code": "4A8",
                "origin": "batch",
                "batch_id": record["id"],
                "taken_at": "2026-09-15",
                "status": "active",
                "retention": {
                    "sent_at": "2026-09-15",
                    "storage_condition": "refrigerator",
                },
            },
        )
    finally:
        sconn.close()

    at = AppTest.from_file("frontend/batches/detail.py")
    at.session_state["batches_detail_id"] = record["id"]
    at.run()
    assert not at.exception
    assert any("4A8" in at.dataframe[i].value.to_string() for i in range(len(at.dataframe)))
    assert any(m.label == "Samples" and m.value == "1" for m in at.metric)


def test_detail_saves_actual_amounts_without_error(db_path) -> None:
    """The non-dialog save paths (record as it happens) are AppTest-
    drivable: saving the unchanged composition editor must not error."""
    conn = gw.connect(db_path)
    try:
        record = gw.create_batch(conn, _payload())
    finally:
        conn.close()

    at = AppTest.from_file("frontend/batches/detail.py")
    at.session_state["batches_detail_id"] = record["id"]
    at.run()
    _buttons(at, "Save actual amounts")[0].click()
    at.run()
    assert not at.exception

    conn = gw.connect(db_path)
    try:
        updated = gw.get_batch(conn, record["id"])
    finally:
        conn.close()
    assert updated["actual"] == {"composition": []}


def test_detail_save_shows_success_toast(db_path) -> None:
    """A successful save is confirmed non-blockingly by a toast on the
    page run that follows (failures use the result modal instead)."""
    conn = gw.connect(db_path)
    try:
        record = gw.create_batch(conn, _payload())
    finally:
        conn.close()

    at = AppTest.from_file("frontend/batches/detail.py")
    at.session_state["batches_detail_id"] = record["id"]
    at.run()
    assert not at.toast

    _buttons(at, "Save actual amounts")[0].click()
    at.run()
    assert not at.exception
    assert any("Actual amounts saved." in t.value for t in at.toast)
    # Success must not open the blocking result modal.
    assert not any(b.label == "OK" for b in at.button)


def test_detail_save_failure_opens_result_modal(db_path, monkeypatch) -> None:
    """A failed save queues the failure; the next page run opens the
    blocking 'Save result' modal (dialog *opening* works in AppTest even
    though in-dialog widget clicks are not modeled)."""
    conn = gw.connect(db_path)
    try:
        record = gw.create_batch(conn, _payload())
    finally:
        conn.close()

    def _boom(*args, **kwargs):
        raise gw.GatewayError("update failed", problems=["amount must be positive"])

    monkeypatch.setattr(gw, "update_batch", _boom)

    at = AppTest.from_file("frontend/batches/detail.py")
    at.session_state["batches_detail_id"] = record["id"]
    at.run()
    assert not any(b.label == "OK" for b in at.button)

    _buttons(at, "Save actual amounts")[0].click()
    at.run()
    assert not at.exception
    assert any(
        "amount must be positive" in e.value for e in at.error
    )
    assert any(b.label == "OK" for b in at.button)


def test_detail_page_missing_batch(db_path) -> None:
    at = AppTest.from_file("frontend/batches/detail.py")
    at.session_state["batches_detail_id"] = 999
    at.run()
    assert not at.exception
    assert any("no longer exists" in w.value for w in at.warning)


def test_detail_page_without_batch_id(db_path) -> None:
    at = AppTest.from_file("frontend/batches/detail.py")
    at.run()
    assert not at.exception
    assert any("No batch selected" in i.value for i in at.info)
