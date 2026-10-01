"""AppTest behavior tests for the Test Reports pages.

Layer: app behavior (docs/TEST_STRATEGIES.md §4.4) — the pages run
headlessly via streamlit.testing.v1.AppTest; no browser, no network.

Known limitation: streamlit 1.60's AppTest has no st.dialog support, so
report/result create/edit/delete *submission* cannot be driven from
AppTest (any click inside a dialog closes it in the test tree). Those
flows are covered by the gateway/service unit tests, contract tests and
the frontend utils unit tests instead. AppTest here covers page loads,
rendering, dialog opening and navigation.
"""
import pytest
from streamlit.testing.v1 import AppTest

from backend.gateway import samples as samples_gw
from backend.gateway import test_reports as gw
from frontend.test_reports import utils


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Temp dev-DB paths for the pages under test: test_reports (the page
    under test) and samples (result labels read the Samples service)."""
    reports_path = tmp_path / "test_reports.db"
    monkeypatch.setattr(
        "backend.services.test_reports.store.DEV_DB_PATH", reports_path
    )
    monkeypatch.setattr(
        "backend.services.samples.store.DEV_DB_PATH", tmp_path / "samples.db"
    )
    return reports_path


def _report_payload(**overrides) -> dict:
    data = {
        "test_method": "Sensory panel",
        "evaluation_date": "2026-09-20",
        "person_in_charge": "ducphu",
        "methodology": "9-point hedonic",
        "equipment": None,
        "panel": "trained panel A",
        "notes": None,
    }
    data.update(overrides)
    return data


def _result_payload(**overrides) -> dict:
    data = {
        "sample_id": 3,
        "transfer_id": 5,
        "parameter": "Overall liking",
        "value": 7.5,
        "unit": "pts",
        "notes": None,
    }
    data.update(overrides)
    return data


def _seed_report(db_path, result: bool = False) -> dict:
    conn = gw.connect(db_path)
    try:
        record = gw.create_report(conn, _report_payload())
        if result:
            gw.create_result(conn, record["id"], _result_payload())
        return record
    finally:
        conn.close()


def _seed_sample(tmp_path) -> dict:
    """Seed a sample with its retention transfer via the Samples service."""
    conn = samples_gw.connect(tmp_path / "samples.db")
    try:
        return samples_gw.create_sample(
            conn,
            {
                "sample_code": "4A8",
                "origin": "batch",
                "batch_id": 12,
                "taken_at": "2026-09-15",
                "status": "active",
                "retention": {
                    "sent_at": "2026-09-15",
                    "storage_condition": "refrigerator",
                },
            },
        )
    finally:
        conn.close()


def _page() -> AppTest:
    return AppTest.from_file("frontend/test_reports/app.py")


def _detail() -> AppTest:
    return AppTest.from_file("frontend/test_reports/detail.py")


def _buttons(at: AppTest, label: str):
    return [b for b in at.button if b.label == label]


# --- overview --------------------------------------------------------------

def test_overview_loads_without_error(db_path) -> None:
    at = _page()
    at.run()
    assert not at.exception
    assert at.title[0].value == "Test Reports"
    assert any("No test reports yet" in i.value for i in at.info)


def test_add_report_opens_dialog(db_path) -> None:
    """The create dialog renders. AppTest cannot submit it."""
    at = _page()
    at.run()
    _buttons(at, "➕ Add report")[0].click()
    at.run()
    assert not at.exception
    assert any("New test report" in m.value for m in at.markdown)


def test_overview_lists_seeded_reports_with_counts(db_path) -> None:
    conn = gw.connect(db_path)
    try:
        first = gw.create_report(
            conn, _report_payload(test_method="Sensory panel")
        )
        gw.create_result(conn, first["id"], _result_payload(sample_id=1))
        gw.create_result(conn, first["id"], _result_payload(sample_id=2))
        gw.create_report(conn, _report_payload(test_method="Stability"))
    finally:
        conn.close()

    at = _page()
    at.run()
    assert not at.exception
    assert not any("No test reports yet" in i.value for i in at.info)
    df = at.dataframe[0].value
    assert set(df["method"]) == {"Sensory panel", "Stability"}
    # most recent report first (lab-notebook order)
    assert df.iloc[0]["method"] == "Stability"
    sensory = df[df["method"] == "Sensory panel"].iloc[0]
    assert sensory["samples"] == 2
    assert sensory["results"] == 2
    assert sensory["in_charge"] == "ducphu"


def test_stale_selection_after_delete_does_not_crash(db_path) -> None:
    """Deleting a selected row leaves the frontend holding the old row
    index; the overview must not index past the end of the smaller table."""
    conn = gw.connect(db_path)
    try:
        gw.create_report(conn, _report_payload(test_method="A"))
        second = gw.create_report(conn, _report_payload(test_method="B"))
    finally:
        conn.close()

    at = _page()
    at.run()
    at.session_state[utils.REPORTS_TABLE_KEY] = {"selection": {"rows": [1]}}
    at.run()
    assert not at.exception
    assert any(b.label == "🗑️ Delete" for b in at.button)

    conn = gw.connect(db_path)
    try:
        gw.delete_report(conn, second["id"])
    finally:
        conn.close()
    at.session_state[utils.REPORTS_TABLE_KEY] = {"selection": {"rows": [1]}}
    at.run()
    assert not at.exception
    assert len(at.dataframe[0].value) == 1
    assert any("Select a report" in c.value for c in at.caption)
    assert not any(b.label == "🗑️ Delete" for b in at.button)


# --- detail ----------------------------------------------------------------

def test_detail_page_loads_via_session_state(db_path) -> None:
    record = _seed_report(db_path)

    at = _detail()
    at.session_state["test_reports_detail_id"] = record["id"]
    at.run()
    assert not at.exception
    assert at.title[0].value == "Sensory panel"
    # Overview + Results tabs render (Analysis is reserved, not rendered)
    assert len(at.tabs) == 2
    assert any(m.label == "Person in charge" for m in at.metric)
    assert any("No results yet" in i.value for i in at.info)
    assert any(b.label == "➕ Add result" for b in at.button)


def test_detail_with_results_offers_manage_actions(db_path) -> None:
    record = _seed_report(db_path, result=True)

    at = _detail()
    at.session_state["test_reports_detail_id"] = record["id"]
    at.run()
    assert not at.exception
    assert any(b.label == "✏️ Edit result" for b in at.button)
    assert any(b.label == "🗑️ Delete result" for b in at.button)
    # results table shows the fallback sample id (no samples service rows)
    df = at.dataframe[0].value
    assert df.iloc[0]["sample"] == "#3"
    assert df.iloc[0]["parameter"] == "Overall liking"
    assert df.iloc[0]["value"] == 7.5


def test_detail_add_result_dialog_lists_samples(db_path, tmp_path) -> None:
    _seed_sample(tmp_path)
    record = _seed_report(db_path)

    at = _detail()
    at.session_state["test_reports_detail_id"] = record["id"]
    at.run()
    _buttons(at, "➕ Add result")[0].click()
    at.run()
    assert not at.exception
    assert any("Add result" in m.value for m in at.markdown)
    sample_select = next(
        (s for s in at.selectbox if s.label == "Sample *"), None
    )
    assert sample_select is not None
    assert "4A8 — batch" in sample_select.options
