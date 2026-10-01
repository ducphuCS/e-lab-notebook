"""Unit tests for the test_reports gateway client.

Layer: unit — gateway (docs/TEST_STRATEGIES.md §4.1/§6): the gateway is
headless (no streamlit) and calls the store in-process. Covers create /
update / delete for reports and results, validation propagation, the
cross-record guard (a result needs its report), and the reverse-link
helpers the Samples/Batches pages consume.
"""
import pytest

from backend.gateway import test_reports as gw


@pytest.fixture()
def conn():
    connection = gw.connect()  # in-memory
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


# --- reports ---------------------------------------------------------------

def test_create_report_returns_record(conn) -> None:
    record = gw.create_report(conn, _report())
    assert record["test_method"] == "Sensory panel"
    assert record["evaluation_date"] == "2026-09-20"
    assert record["person_in_charge"] == "ducphu"


def test_create_report_invalid_payload_raises(conn) -> None:
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.create_report(conn, _report(test_method=""))
    assert any("test_method" in p for p in excinfo.value.problems)


def test_get_report(conn) -> None:
    record = gw.create_report(conn, _report())
    assert gw.get_report(conn, record["id"]) == record
    assert gw.get_report(conn, 999) is None


def test_update_report_mutable_fields(conn) -> None:
    record = gw.create_report(conn, _report())
    updated = gw.update_report(
        conn, record["id"], {"notes": "final", "panel": "panel B"}
    )
    assert updated["notes"] == "final"
    assert updated["panel"] == "panel B"
    assert updated["test_method"] == "Sensory panel"


def test_update_report_invalid_merge_raises(conn) -> None:
    record = gw.create_report(conn, _report())
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.update_report(conn, record["id"], {"evaluation_date": "nope"})
    assert any("evaluation_date" in p for p in excinfo.value.problems)


def test_update_report_not_found_raises(conn) -> None:
    with pytest.raises(gw.GatewayError):
        gw.update_report(conn, 999, {"notes": "x"})


def test_delete_report_cascades_results(conn) -> None:
    record = gw.create_report(conn, _report())
    gw.create_result(conn, record["id"], _result())
    assert gw.delete_report(conn, record["id"]) is True
    assert gw.get_report(conn, record["id"]) is None
    assert gw.list_results(conn, record["id"]) == []


def test_delete_report_not_found_raises(conn) -> None:
    with pytest.raises(gw.GatewayError):
        gw.delete_report(conn, 999)


# --- results ---------------------------------------------------------------

def test_create_result(conn) -> None:
    report = gw.create_report(conn, _report())
    result = gw.create_result(conn, report["id"], _result())
    assert result["report_id"] == report["id"]
    assert result["sample_id"] == 3
    assert result["parameter"] == "Overall liking"
    assert result["value"] == 7.5


def test_create_result_requires_existing_report(conn) -> None:
    with pytest.raises(gw.GatewayError):
        gw.create_result(conn, 999, _result())


def test_create_result_invalid_payload_raises(conn) -> None:
    report = gw.create_report(conn, _report())
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.create_result(conn, report["id"], _result(value="high"))
    assert any("value" in p for p in excinfo.value.problems)


def test_update_result_and_report_id_is_fixed(conn) -> None:
    report = gw.create_report(conn, _report())
    result = gw.create_result(conn, report["id"], _result())
    updated = gw.update_result(
        conn, result["id"], {"value": 8.0, "report_id": 999}
    )
    assert updated["value"] == 8.0
    assert updated["report_id"] == report["id"]


def test_update_result_not_found_raises(conn) -> None:
    with pytest.raises(gw.GatewayError):
        gw.update_result(conn, 999, {"value": 1})


def test_delete_result(conn) -> None:
    report = gw.create_report(conn, _report())
    result = gw.create_result(conn, report["id"], _result())
    assert gw.delete_result(conn, result["id"]) is True
    assert gw.get_result(conn, result["id"]) is None


# --- reverse links (Samples / Batches pages) -------------------------------

def test_reverse_link_helpers(conn) -> None:
    first = gw.create_report(conn, _report(test_method="A"))
    second = gw.create_report(conn, _report(test_method="B"))
    gw.create_result(conn, first["id"], _result(sample_id=1))
    gw.create_result(conn, second["id"], _result(sample_id=1))
    gw.create_result(conn, second["id"], _result(sample_id=2))

    assert gw.count_reports_by_sample_id(conn) == {1: 2, 2: 1}
    assert gw.count_results_by_transfer_id(conn, 5) == 3
    assert gw.count_results_by_transfer_id(conn, 99) == 0
    assert gw.result_stats_by_report_id(conn) == {
        first["id"]: {"results": 1, "samples": 1},
        second["id"]: {"results": 2, "samples": 2},
    }
    # the union of reports touching samples 1 and 2 is {A, B}
    assert gw.count_reports_by_sample_ids(conn, [1, 2]) == 2
    assert gw.count_reports_by_sample_ids(conn, []) == 0

    rows = gw.list_results_by_sample(conn, 1)
    assert len(rows) == 2
    assert set(rows[0]) == {
        "id",
        "report_id",
        "test_method",
        "evaluation_date",
        "parameter",
        "value",
        "unit",
        "transfer_id",
    }

    # unknown result id
    with pytest.raises(gw.GatewayError):
        gw.delete_result(conn, 999)


def test_validate_result_summary() -> None:
    good = {
        "id": 1,
        "report_id": 1,
        "test_method": "Sensory panel",
        "evaluation_date": "2026-09-20",
        "parameter": "Overall liking",
        "value": 7.5,
        "unit": "pts",
        "transfer_id": 5,
    }
    assert gw.validate_result_summary(good) == []

    bad = {
        "id": "x",
        "report_id": None,
        "test_method": "",
        "evaluation_date": None,
        "parameter": "",
        "value": "high",
        "unit": 5,
        "transfer_id": None,
    }
    problems = gw.validate_result_summary(bad)
    assert any("id" in p for p in problems)
    assert any("value" in p for p in problems)
