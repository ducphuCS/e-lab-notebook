"""AppTest behavior tests for the Samples pages.

Layer: app behavior (docs/TEST_STRATEGIES.md §4.4) — the pages run
headlessly via streamlit.testing.v1.AppTest; no browser, no network.

Known limitation: streamlit 1.60's AppTest has no st.dialog support, so
sample/dispatch create/edit/delete *submission* cannot be driven from
AppTest (any click inside a dialog closes it in the test tree). Those
flows are covered by the gateway/service unit tests, contract tests and
the frontend utils unit tests instead. AppTest here covers page loads,
rendering, dialog opening and navigation.
"""
import pytest
from streamlit.testing.v1 import AppTest

from backend.gateway import samples as gw
from backend.gateway import test_reports as tr_gw
from backend.services.batches import store as batches_store
from frontend.samples import utils


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    """Temp dev-DB paths for the pages under test: samples (the page under
    test) and batches (the origin column/links read the Batches service)."""
    samples_path = tmp_path / "samples.db"
    monkeypatch.setattr(
        "backend.services.samples.store.DEV_DB_PATH", samples_path
    )
    monkeypatch.setattr(
        "backend.services.batches.store.DEV_DB_PATH",
        tmp_path / "batches.db",
    )
    monkeypatch.setattr(
        "backend.services.test_reports.store.DEV_DB_PATH",
        tmp_path / "test_reports.db",
    )
    return samples_path


def _payload(code: str = "4A8", batch_id: int | None = 12, **overrides) -> dict:
    data = {
        "sample_code": code,
        "origin": "batch" if batch_id is not None else "benchmark",
        "batch_id": batch_id,
        "source": None,
        "taken_at": "2026-09-15",
        "status": "active",
        "notes": None,
        "retention": {
            "sent_at": "2026-09-15",
            "storage_condition": "refrigerator",
        },
    }
    data.update(overrides)
    return data


def _seed_batch(tmp_path, name: str = "Run") -> int:
    """Seed a batch directly through the dumb store (no validation)."""
    conn = batches_store.connect(tmp_path / "batches.db")
    try:
        return batches_store.create_batch(
            conn,
            {
                "name": name,
                "formula_id": 5,
                "formula_name": "Emulsion X",
                "formula_version": 1,
                "planned": {},
                "actual": {},
            },
        )
    finally:
        conn.close()


def _page() -> AppTest:
    return AppTest.from_file("frontend/samples/app.py")


def _buttons(at: AppTest, label: str):
    return [b for b in at.button if b.label == label]


# --- overview --------------------------------------------------------------

def test_page_loads_without_error(db_path) -> None:
    at = _page()
    at.run()
    assert not at.exception
    assert at.title[0].value == "Samples"
    assert any("No samples yet" in i.value for i in at.info)


def test_add_sample_opens_dialog(db_path) -> None:
    """The create dialog renders. AppTest cannot submit it; with no batches
    yet it explains there is nothing to attach a batch sample to."""
    at = _page()
    at.run()
    _buttons(at, "➕ Add sample")[0].click()
    at.run()
    assert not at.exception
    assert any("New sample" in m.value for m in at.markdown)
    assert any("No batches yet" in w.value for w in at.warning)


def test_overview_lists_seeded_samples(db_path) -> None:
    conn = gw.connect(db_path)
    try:
        gw.create_sample(conn, _payload(sample_code="AAA"))
        second = gw.create_sample(conn, _payload(sample_code="BBB"))
        gw.create_transfer(
            conn,
            second["id"],
            {
                "kind": "dispatch",
                "to_team": "shelf-life",
                "sent_at": "2026-10-01",
                "storage_condition": "TA45",
            },
        )
    finally:
        conn.close()

    at = _page()
    at.run()
    assert not at.exception
    assert not any("No samples yet" in i.value for i in at.info)
    df = at.dataframe[0].value
    assert set(df["code"]) == {"AAA", "BBB"}
    assert set(df["origin"]) == {"batch #12"}
    assert set(df["status"]) == {"active"}
    # most recent sample first (lab-notebook order)
    assert df.iloc[0]["code"] == "BBB"
    assert df.iloc[0]["dispatches"] == 1
    assert df.iloc[0]["reports"] == 0


def test_overview_shows_batch_origin_when_batch_exists(db_path, tmp_path) -> None:
    batch_id = _seed_batch(tmp_path)
    conn = gw.connect(db_path)
    try:
        gw.create_sample(conn, _payload(batch_id=batch_id))
    finally:
        conn.close()

    at = _page()
    at.run()
    assert not at.exception
    df = at.dataframe[0].value
    assert df.iloc[0]["origin"] == "batch B-0001"


def test_status_filter_narrows_table(db_path) -> None:
    conn = gw.connect(db_path)
    try:
        gw.create_sample(conn, _payload(sample_code="AAA", status="active"))
        gw.create_sample(conn, _payload(sample_code="BBB", status="depleted"))
    finally:
        conn.close()

    at = _page()
    at.run()
    # the Status filter is the only filter (no batch records to filter by)
    at.selectbox[0].select("depleted")
    at.run()
    assert not at.exception
    df = at.dataframe[0].value
    assert list(df["code"]) == ["BBB"]


def test_stale_selection_after_delete_does_not_crash(db_path) -> None:
    """Deleting a selected row leaves the frontend holding the old row
    index; the overview must not index past the end of the smaller table."""
    conn = gw.connect(db_path)
    try:
        gw.create_sample(conn, _payload(sample_code="AAA"))
        second = gw.create_sample(conn, _payload(sample_code="BBB"))
    finally:
        conn.close()

    at = _page()
    at.run()
    at.session_state[utils.SAMPLES_TABLE_KEY] = {"selection": {"rows": [1]}}
    at.run()
    assert not at.exception
    assert any(b.label == "🗑️ Delete" for b in at.button)

    # the second sample is deleted behind the scenes; the frontend echoes
    # the STALE selection (rows=[1]) on the rerun.
    conn = gw.connect(db_path)
    try:
        gw.delete_sample(conn, second["id"])
    finally:
        conn.close()
    at.session_state[utils.SAMPLES_TABLE_KEY] = {"selection": {"rows": [1]}}
    at.run()
    assert not at.exception
    assert len(at.dataframe[0].value) == 1
    assert any("Select a sample" in c.value for c in at.caption)
    assert not any(b.label == "🗑️ Delete" for b in at.button)


# --- detail ----------------------------------------------------------------

def test_detail_page_loads_via_session_state(db_path) -> None:
    """Detail page with the sample id from session_state (AppTest cannot
    set query params)."""
    conn = gw.connect(db_path)
    try:
        record = gw.create_sample(conn, _payload())
    finally:
        conn.close()

    at = AppTest.from_file("frontend/samples/detail.py")
    at.session_state["samples_detail_id"] = record["id"]
    at.run()
    assert not at.exception
    assert at.title[0].value == "4A8"
    assert any("status: active" in c.value for c in at.caption)
    # all three tabs render
    assert len(at.tabs) == 3
    # retention is shown read-only; no dispatches yet
    assert any(m.label == "Storage condition" for m in at.metric)
    assert any("No dispatches yet" in c.value for c in at.caption)
    assert any(b.label == "➕ Dispatch to a team" for b in at.button)
    # test reports tab is live, empty
    assert any("No test reports for this sample yet" in i.value for i in at.info)


def test_detail_with_dispatch_offers_manage_actions(db_path) -> None:
    conn = gw.connect(db_path)
    try:
        record = gw.create_sample(conn, _payload())
        gw.create_transfer(
            conn,
            record["id"],
            {
                "kind": "dispatch",
                "to_team": "microbiology",
                "sent_at": "2026-10-01",
                "storage_condition": "TA35",
            },
        )
    finally:
        conn.close()

    at = AppTest.from_file("frontend/samples/detail.py")
    at.session_state["samples_detail_id"] = record["id"]
    at.run()
    assert not at.exception
    assert any(b.label == "✏️ Edit dispatch" for b in at.button)
    assert any(b.label == "🗑️ Delete dispatch" for b in at.button)
    # transfer history table renders
    assert at.dataframe[0].value.iloc[0]["kind"] == "dispatch"


def test_detail_add_dispatch_opens_dialog(db_path) -> None:
    conn = gw.connect(db_path)
    try:
        record = gw.create_sample(conn, _payload())
    finally:
        conn.close()

    at = AppTest.from_file("frontend/samples/detail.py")
    at.session_state["samples_detail_id"] = record["id"]
    at.run()
    _buttons(at, "➕ Dispatch to a team")[0].click()
    at.run()
    assert not at.exception
    assert any("Dispatch 4A8" in m.value for m in at.markdown)


def test_detail_page_missing_sample(db_path) -> None:
    at = AppTest.from_file("frontend/samples/detail.py")
    at.session_state["samples_detail_id"] = 999
    at.run()
    assert not at.exception
    assert any("no longer exists" in w.value for w in at.warning)


def test_detail_page_without_sample_id(db_path) -> None:
    at = AppTest.from_file("frontend/samples/detail.py")
    at.run()
    assert not at.exception
    assert any("No sample selected" in i.value for i in at.info)


# --- Test Reports reverse link (README §6 / Test Reports Q13) --------------

def _seed_report(tmp_path, sample_id: int, transfer_id: int) -> None:
    """Seed a report with one result anchored to a sample+transfer."""
    conn = tr_gw.connect(tmp_path / "test_reports.db")
    try:
        report = tr_gw.create_report(
            conn,
            {"test_method": "Sensory panel", "evaluation_date": "2026-09-20"},
        )
        tr_gw.create_result(
            conn,
            report["id"],
            {
                "sample_id": sample_id,
                "transfer_id": transfer_id,
                "parameter": "Overall liking",
                "value": 7.5,
                "unit": "pts",
            },
        )
    finally:
        conn.close()


def test_overview_shows_real_report_count(db_path, tmp_path) -> None:
    conn = gw.connect(db_path)
    try:
        record = gw.create_sample(conn, _payload())
        retention = gw.list_transfers(conn, record["id"])[0]
    finally:
        conn.close()
    _seed_report(tmp_path, record["id"], retention["id"])

    at = _page()
    at.run()
    assert not at.exception
    assert at.dataframe[0].value.iloc[0]["reports"] == 1


def test_delete_dialog_blocked_by_test_report(db_path, tmp_path) -> None:
    conn = gw.connect(db_path)
    try:
        record = gw.create_sample(conn, _payload())
        retention = gw.list_transfers(conn, record["id"])[0]
    finally:
        conn.close()
    _seed_report(tmp_path, record["id"], retention["id"])

    at = _page()
    at.session_state[utils.SAMPLES_TABLE_KEY] = {"selection": {"rows": [0]}}
    at.run()
    _buttons(at, "🗑️ Delete")[0].click()
    at.run()
    assert not at.exception
    assert any("test report" in w.value for w in at.warning)


def test_transfer_pinned_by_result(db_path, tmp_path) -> None:
    conn = gw.connect(db_path)
    try:
        record = gw.create_sample(conn, _payload())
        dispatch = gw.create_transfer(
            conn,
            record["id"],
            {
                "kind": "dispatch",
                "to_team": "shelf-life",
                "sent_at": "2026-10-01",
                "storage_condition": "TA45",
            },
        )
    finally:
        conn.close()
    _seed_report(tmp_path, record["id"], dispatch["id"])

    at = AppTest.from_file("frontend/samples/detail.py")
    at.session_state["samples_detail_id"] = record["id"]
    at.run()
    _buttons(at, "🗑️ Delete dispatch")[0].click()
    at.run()
    assert not at.exception
    assert any("cannot be deleted" in w.value for w in at.warning)
