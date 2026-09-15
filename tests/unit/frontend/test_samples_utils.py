"""Unit tests for the pure Samples page helpers.

Layer: unit — frontend (docs/TEST_STRATEGIES.md §4.2). Pure functions, no
streamlit runtime: identity (code suggestion/normalization), age in weeks,
overview rows, filters, the delete-guard reason and the payload builders.
"""
import random
from datetime import date

from frontend.samples import utils


def _record(**overrides) -> dict:
    data = {
        "id": 1,
        "sample_code": "4A8",
        "origin": "batch",
        "batch_id": 12,
        "source": None,
        "taken_at": "2026-09-15",
        "status": "active",
        "notes": None,
        "created_at": "2026-09-15T10:00:00+00:00",
        "updated_at": "2026-09-15T10:00:00+00:00",
    }
    data.update(overrides)
    return data


def _transfer(kind: str, **overrides) -> dict:
    data = {
        "id": 1,
        "sample_id": 1,
        "kind": kind,
        "to_team": None if kind == "retention" else "shelf-life",
        "sent_at": "2026-09-15",
        "storage_condition": "TA35",
        "sent_by": None,
        "notes": None,
    }
    data.update(overrides)
    return data


# --- identity (Q3/Q11) -----------------------------------------------------

def test_normalize_sample_code() -> None:
    assert utils.normalize_sample_code(" a9z ") == "A9Z"
    assert utils.normalize_sample_code(None) == ""


def test_suggest_sample_code_shape_and_exclusion() -> None:
    rng = random.Random(0)
    existing = ["4A8", "ZZZ"]
    for _ in range(50):
        code = utils.suggest_sample_code(existing, rng=rng)
        assert len(code) == 3
        assert all(char in "ABCDEFGHJKMNPQRSTUVWXYZ23456789" for char in code)
        assert code not in existing


def test_suggest_sample_code_never_ambiguous() -> None:
    rng = random.Random(1)
    for _ in range(200):
        code = utils.suggest_sample_code(rng=rng)
        assert not (set(code) & set("ILO01"))


# --- age in weeks (Q2) -----------------------------------------------------

def test_parse_date() -> None:
    assert utils.parse_date("2026-09-15") == date(2026, 9, 15)
    assert utils.parse_date("2026-09-15T10:00:00+00:00") == date(2026, 9, 15)
    assert utils.parse_date(None) is None
    assert utils.parse_date("not a date") is None


def test_weeks_since_boundaries() -> None:
    assert utils.weeks_since("2026-09-01", date(2026, 9, 15)) == 2
    assert utils.weeks_since("2026-09-01", date(2026, 9, 7)) == 0
    assert utils.weeks_since("2026-09-01", date(2026, 9, 8)) == 1
    # future dates count as 0 weeks
    assert utils.weeks_since("2026-09-20", date(2026, 9, 15)) == 0
    assert utils.weeks_since("oops") is None


# --- transfer selectors ----------------------------------------------------

def test_retention_and_dispatches() -> None:
    transfers = [
        _transfer("dispatch", id=2, sent_at="2026-10-01"),
        _transfer("retention", id=1),
    ]
    assert utils.retention(transfers)["id"] == 1
    assert [t["id"] for t in utils.dispatches(transfers)] == [2]
    assert utils.transfer_count(transfers) == 2
    assert utils.transfer_count(transfers, kind="dispatch") == 1
    assert utils.retention([]) is None


def test_transfer_rows_newest_first() -> None:
    transfers = [
        _transfer("retention", id=1, sent_at="2026-09-15"),
        _transfer(
            "dispatch",
            id=2,
            sent_at="2026-10-01",
            storage_condition="TA45",
            sent_by="ducphu",
        ),
    ]
    rows = utils.transfer_rows(transfers)
    assert len(rows) == 2
    assert rows[0]["kind"] == "dispatch"
    assert rows[0]["storage"] == "TA45"
    assert rows[0]["by"] == "ducphu"
    assert rows[1]["team"] == "—"


# --- overview --------------------------------------------------------------

def test_origin_label() -> None:
    index = {12: {"batch_code": "B-0001"}}
    assert utils.origin_label(_record(), index) == "batch B-0001"
    assert (
        utils.origin_label(
            _record(origin="benchmark", batch_id=None), index
        )
        == "benchmark"
    )
    assert utils.origin_label(_record(), {}) == "batch #12"


def test_overview_rows() -> None:
    records = [_record(), _record(id=2, sample_code="BBB", origin="benchmark", batch_id=None)]
    index = {12: {"batch_code": "B-0001"}}
    counts = {1: {"total": 2, "dispatches": 1}}
    rows = utils.overview_rows(records, index, counts)
    assert rows[0]["code"] == "4A8"
    assert rows[0]["origin"] == "batch B-0001"
    assert rows[0]["age_weeks"] is not None
    assert rows[0]["dispatches"] == 1
    assert rows[0]["reports"] == 0
    assert rows[1]["origin"] == "benchmark"
    assert rows[1]["dispatches"] == 0


def test_filter_samples() -> None:
    records = [
        _record(id=1, status="active", batch_id=12),
        _record(id=2, status="depleted", batch_id=12),
        _record(id=3, status="active", batch_id=13),
        _record(id=4, origin="benchmark", batch_id=None),
    ]
    assert [r["id"] for r in utils.filter_samples(records, status="active")] == [1, 3, 4]
    assert [r["id"] for r in utils.filter_samples(records, batch_id=12)] == [1, 2]
    assert [
        r["id"]
        for r in utils.filter_samples(records, status="active", batch_id=13)
    ] == [3]
    assert len(utils.filter_samples(records)) == 4


def test_batch_options() -> None:
    options, label_to_id = utils.batch_options(
        [
            {"id": 1, "batch_code": "B-0001", "name": "First"},
            {"id": 2, "batch_code": "B-0002", "name": "Second"},
        ]
    )
    assert options == ["B-0001 — First", "B-0002 — Second"]
    assert label_to_id["B-0001 — First"] == 1


# --- delete guard (Q8/Q12) -------------------------------------------------

def test_sample_delete_block_reason() -> None:
    assert utils.sample_delete_block_reason(0, 0) is None
    assert "dispatch" in utils.sample_delete_block_reason(1, 0)
    assert "test report" in utils.sample_delete_block_reason(0, 1)
    reason = utils.sample_delete_block_reason(2, 3)
    assert "test report" in reason and "dispatch" in reason


# --- payload builders ------------------------------------------------------

def test_build_sample_payload() -> None:
    payload = utils.build_sample_payload(
        sample_code=" a9z ",
        origin="batch",
        batch_id=12,
        source="  ",
        taken_at="2026-09-15",
        status="active",
        notes="  note  ",
        retention_storage="TA35",
    )
    assert payload["sample_code"] == "A9Z"
    assert payload["source"] is None
    assert payload["notes"] == "note"
    # the retention transfer always defaults sent_at to the taken date
    assert payload["retention"] == {
        "sent_at": "2026-09-15",
        "storage_condition": "TA35",
        "sent_by": None,
        "notes": None,
    }


def test_build_sample_payload_benchmark() -> None:
    payload = utils.build_sample_payload(
        sample_code="4A8",
        origin="benchmark",
        batch_id=None,
        source="Brand X",
        taken_at="2026-09-15",
        retention_storage="room temperature",
    )
    assert payload["origin"] == "benchmark"
    assert payload["batch_id"] is None
    assert payload["source"] == "Brand X"


def test_build_transfer_payload() -> None:
    payload = utils.build_transfer_payload(
        to_team=" shelf-life ",
        sent_at="2026-10-01",
        storage_condition="TA45",
        sent_by="",
        notes="  ",
    )
    assert payload == {
        "kind": "dispatch",
        "to_team": "shelf-life",
        "sent_at": "2026-10-01",
        "storage_condition": "TA45",
        "sent_by": None,
        "notes": None,
    }
