"""Unit tests for the SQLite test-report store.

Layer: unit — backend (docs/TEST_STRATEGIES.md §4.1). Uses an in-memory
database; no files, no network.
"""
import pytest

from backend.services.test_reports import store


@pytest.fixture()
def conn():
    connection = store.connect()  # in-memory
    yield connection
    connection.close()


def _report(**overrides) -> dict:
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


def _result(**overrides) -> dict:
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


def _create(conn, report=None, result=None) -> tuple[int, int]:
    report_id = store.create_report(conn, report or _report())
    result_id = store.create_result(conn, report_id, result or _result())
    return report_id, result_id


# --- reports ---------------------------------------------------------------

def test_create_and_get_report(conn) -> None:
    report_id = store.create_report(conn, _report())
    record = store.get_report(conn, report_id)
    assert record["test_method"] == "Sensory panel"
    assert record["evaluation_date"] == "2026-09-20"
    assert record["person_in_charge"] == "ducphu"
    assert record["methodology"] == "9-point hedonic"
    assert record["created_at"] and record["updated_at"]


def test_create_report_defaults_optional_fields_to_none(conn) -> None:
    report_id = store.create_report(
        conn, {"test_method": "Stability", "evaluation_date": "2026-09-21"}
    )
    record = store.get_report(conn, report_id)
    assert record["person_in_charge"] is None
    assert record["equipment"] is None
    assert record["panel"] is None


def test_list_reports_newest_first(conn) -> None:
    first = store.create_report(conn, _report(test_method="A"))
    second = store.create_report(conn, _report(test_method="B"))
    assert [r["id"] for r in store.list_reports(conn)] == [second, first]


def test_get_missing_report_returns_none(conn) -> None:
    assert store.get_report(conn, 999) is None


def test_update_report_partial_merge(conn) -> None:
    report_id = store.create_report(conn, _report())
    assert store.update_report(conn, report_id, {"notes": "final"})
    record = store.get_report(conn, report_id)
    assert record["notes"] == "final"
    # untouched
    assert record["test_method"] == "Sensory panel"


def test_update_missing_report_returns_false(conn) -> None:
    assert store.update_report(conn, 999, {"notes": "x"}) is False


def test_delete_report_cascades_results(conn) -> None:
    report_id, _ = _create(conn)
    assert store.delete_report(conn, report_id) is True
    assert store.get_report(conn, report_id) is None
    assert store.list_results(conn, report_id) == []


def test_delete_missing_report_returns_false(conn) -> None:
    assert store.delete_report(conn, 999) is False


# --- results ---------------------------------------------------------------

def test_create_result(conn) -> None:
    report_id = store.create_report(conn, _report())
    result_id = store.create_result(conn, report_id, _result())
    record = store.get_result(conn, result_id)
    assert record["report_id"] == report_id
    assert record["sample_id"] == 3
    assert record["transfer_id"] == 5
    assert record["parameter"] == "Overall liking"
    assert record["value"] == 7.5
    assert record["unit"] == "pts"
    assert record["created_at"] and record["updated_at"]


def test_list_results_in_insertion_order(conn) -> None:
    report_id = store.create_report(conn, _report())
    first = store.create_result(conn, report_id, _result(sample_id=1))
    second = store.create_result(conn, report_id, _result(sample_id=2))
    assert [r["id"] for r in store.list_results(conn, report_id)] == [
        first,
        second,
    ]


def test_get_missing_result_returns_none(conn) -> None:
    assert store.get_result(conn, 999) is None


def test_update_result_partial_merge(conn) -> None:
    _, result_id = _create(conn)
    assert store.update_result(
        conn, result_id, {"value": 8.0, "notes": "re-read"}
    )
    record = store.get_result(conn, result_id)
    assert record["value"] == 8.0
    assert record["notes"] == "re-read"
    assert record["parameter"] == "Overall liking"


def test_update_result_never_rewrites_report_id(conn) -> None:
    report_id, result_id = _create(conn)
    store.update_result(conn, result_id, {"report_id": 999})
    assert store.get_result(conn, result_id)["report_id"] == report_id


def test_delete_result(conn) -> None:
    _, result_id = _create(conn)
    assert store.delete_result(conn, result_id) is True
    assert store.get_result(conn, result_id) is None


def test_delete_missing_result_returns_false(conn) -> None:
    assert store.delete_result(conn, 999) is False


# --- reverse links (Samples / Batches pages) -------------------------------

def test_count_reports_by_sample_id_counts_distinct_reports(conn) -> None:
    first = store.create_report(conn, _report(test_method="A"))
    second = store.create_report(conn, _report(test_method="B"))
    # sample 1 -> two reports; sample 2 -> one report (two rows)
    store.create_result(conn, first, _result(sample_id=1))
    store.create_result(conn, second, _result(sample_id=1))
    store.create_result(conn, second, _result(sample_id=2, parameter="Colour"))
    store.create_result(conn, second, _result(sample_id=2, parameter="Odour"))
    assert store.count_reports_by_sample_id(conn) == {1: 2, 2: 1}


def test_count_results_by_transfer_id(conn) -> None:
    report_id = store.create_report(conn, _report())
    store.create_result(conn, report_id, _result(transfer_id=5))
    store.create_result(conn, report_id, _result(transfer_id=5, parameter="Colour"))
    store.create_result(conn, report_id, _result(transfer_id=6))
    assert store.count_results_by_transfer_id(conn, 5) == 2
    assert store.count_results_by_transfer_id(conn, 6) == 1
    assert store.count_results_by_transfer_id(conn, 99) == 0


def test_result_stats_by_report_id(conn) -> None:
    first = store.create_report(conn, _report())
    second = store.create_report(conn, _report())
    store.create_result(conn, first, _result(sample_id=1))
    store.create_result(conn, first, _result(sample_id=1, parameter="Colour"))
    store.create_result(conn, first, _result(sample_id=2))
    store.create_result(conn, second, _result(sample_id=1))
    assert store.result_stats_by_report_id(conn) == {
        first: {"results": 3, "samples": 2},
        second: {"results": 1, "samples": 1},
    }


def test_count_reports_by_sample_ids_counts_a_report_once(conn) -> None:
    report_id = store.create_report(conn, _report())
    store.create_result(conn, report_id, _result(sample_id=1))
    store.create_result(conn, report_id, _result(sample_id=2))
    assert store.count_reports_by_sample_ids(conn, [1, 2]) == 1
    assert store.count_reports_by_sample_ids(conn, []) == 0
    assert store.count_reports_by_sample_ids(conn, [99]) == 0


def test_list_results_by_sample_joins_report_info(conn) -> None:
    report_id = store.create_report(
        conn, _report(test_method="Sensory panel")
    )
    store.create_result(conn, report_id, _result(sample_id=3, value=7.5))
    rows = store.list_results_by_sample(conn, 3)
    assert len(rows) == 1
    assert rows[0]["test_method"] == "Sensory panel"
    assert rows[0]["evaluation_date"] == "2026-09-20"
    assert rows[0]["parameter"] == "Overall liking"
    assert rows[0]["value"] == 7.5
    assert rows[0]["unit"] == "pts"
    assert rows[0]["transfer_id"] == 5
    assert store.list_results_by_sample(conn, 999) == []


def test_list_results_by_sample_newest_evaluation_first(conn) -> None:
    old = store.create_report(conn, _report(evaluation_date="2026-01-01"))
    new = store.create_report(conn, _report(evaluation_date="2026-09-20"))
    store.create_result(conn, old, _result(sample_id=3))
    store.create_result(conn, new, _result(sample_id=3))
    rows = store.list_results_by_sample(conn, 3)
    assert [r["report_id"] for r in rows] == [new, old]
