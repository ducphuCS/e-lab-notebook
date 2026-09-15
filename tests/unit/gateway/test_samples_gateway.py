"""Unit tests for the samples gateway client (policy guards).

Layer: unit — gateway (docs/TEST_STRATEGIES.md §4.1/§6): the gateway is
headless (no streamlit) and calls the store in-process. Covers the policy
guards from README Q7/Q8/Q11/Q12 — immutable identity/provenance, the one
retention invariant, the read-only retention row, code uniqueness and the
delete guard — plus validation propagation.
"""
import pytest

from backend.gateway import samples as gw


@pytest.fixture()
def conn():
    connection = gw.connect()  # in-memory
    yield connection
    connection.close()


def _payload(**overrides) -> dict:
    data = {
        "sample_code": "4A8",
        "origin": "batch",
        "batch_id": 12,
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


def _dispatch(**overrides) -> dict:
    data = {
        "kind": "dispatch",
        "to_team": "shelf-life",
        "sent_at": "2026-10-01",
        "storage_condition": "TA45",
        "sent_by": "ducphu",
        "notes": None,
    }
    data.update(overrides)
    return data


# --- create ----------------------------------------------------------------

def test_create_valid_returns_record_with_retention(conn) -> None:
    record = gw.create_sample(conn, _payload())
    assert record["sample_code"] == "4A8"
    assert record["origin"] == "batch"
    assert record["batch_id"] == 12
    assert record["status"] == "active"

    transfers = gw.list_transfers(conn, record["id"])
    assert len(transfers) == 1
    assert transfers[0]["kind"] == "retention"
    assert transfers[0]["storage_condition"] == "refrigerator"


def test_create_normalizes_code_to_uppercase(conn) -> None:
    record = gw.create_sample(conn, _payload(sample_code=" a9z "))
    assert record["sample_code"] == "A9Z"


def test_create_invalid_payload_raises(conn) -> None:
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.create_sample(conn, _payload(sample_code="oops"))
    assert any("sample_code" in p for p in excinfo.value.problems)


def test_create_requires_retention(conn) -> None:
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.create_sample(conn, _payload(retention=None))
    assert any("retention" in p for p in excinfo.value.problems)


def test_create_rejects_duplicate_code_case_insensitively(conn) -> None:
    gw.create_sample(conn, _payload(sample_code="4A8"))
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.create_sample(conn, _payload(sample_code="4a8", batch_id=13))
    assert any("already in use" in p for p in excinfo.value.problems)


def test_create_benchmark_without_batch(conn) -> None:
    record = gw.create_sample(
        conn, _payload(origin="benchmark", batch_id=None, source="Brand X")
    )
    assert record["origin"] == "benchmark"
    assert record["batch_id"] is None


# --- update ----------------------------------------------------------------

def test_update_not_found_raises(conn) -> None:
    with pytest.raises(gw.GatewayError):
        gw.update_sample(conn, 999, {"status": "depleted"})


def test_update_mutable_fields(conn) -> None:
    record = gw.create_sample(conn, _payload())
    updated = gw.update_sample(
        conn,
        record["id"],
        {"status": "expired", "notes": "past its window"},
    )
    assert updated["status"] == "expired"
    assert updated["notes"] == "past its window"
    assert updated["sample_code"] == "4A8"


def test_identity_and_provenance_are_immutable(conn) -> None:
    record = gw.create_sample(conn, _payload())
    for field, value in [
        ("sample_code", "ZZZ"),
        ("origin", "benchmark"),
        ("batch_id", 99),
    ]:
        with pytest.raises(gw.GatewayError) as excinfo:
            gw.update_sample(conn, record["id"], {field: value})
        assert any(
            "cannot be changed after creation" in p
            for p in excinfo.value.problems
        )


def test_immutable_field_equal_value_passes(conn) -> None:
    record = gw.create_sample(conn, _payload())
    updated = gw.update_sample(
        conn, record["id"], {"sample_code": record["sample_code"]}
    )
    assert updated["sample_code"] == record["sample_code"]


# --- delete guard ----------------------------------------------------------

def test_delete_without_dispatches(conn) -> None:
    record = gw.create_sample(conn, _payload())
    assert gw.delete_sample(conn, record["id"]) is True
    assert gw.get_sample(conn, record["id"]) is None
    assert gw.list_transfers(conn, record["id"]) == []


def test_delete_blocked_by_dispatch(conn) -> None:
    record = gw.create_sample(conn, _payload())
    gw.create_transfer(conn, record["id"], _dispatch())
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.delete_sample(conn, record["id"])
    assert any("dispatch" in p for p in excinfo.value.problems)
    # still there
    assert gw.get_sample(conn, record["id"]) is not None


def test_delete_not_found_raises(conn) -> None:
    with pytest.raises(gw.GatewayError):
        gw.delete_sample(conn, 999)


# --- transfers -------------------------------------------------------------

def test_create_dispatch(conn) -> None:
    record = gw.create_sample(conn, _payload())
    transfer = gw.create_transfer(conn, record["id"], _dispatch())
    assert transfer["kind"] == "dispatch"
    assert transfer["to_team"] == "shelf-life"


def test_create_second_retention_is_refused(conn) -> None:
    record = gw.create_sample(conn, _payload())
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.create_transfer(
            conn,
            record["id"],
            _dispatch(kind="retention", to_team=None),
        )
    assert any("retention" in p for p in excinfo.value.problems)


def test_create_transfer_invalid_payload_raises(conn) -> None:
    record = gw.create_sample(conn, _payload())
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.create_transfer(conn, record["id"], _dispatch(to_team="  "))
    assert any("to_team" in p for p in excinfo.value.problems)


def test_create_transfer_missing_sample_raises(conn) -> None:
    with pytest.raises(gw.GatewayError):
        gw.create_transfer(conn, 999, _dispatch())


def test_retention_row_is_read_only(conn) -> None:
    record = gw.create_sample(conn, _payload())
    retention = gw.list_transfers(conn, record["id"])[0]
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.update_transfer(conn, retention["id"], {"to_team": "x"})
    assert any("read-only" in p for p in excinfo.value.problems)
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.delete_transfer(conn, retention["id"])
    assert any("cannot be deleted" in p for p in excinfo.value.problems)


def test_update_and_delete_dispatch(conn) -> None:
    record = gw.create_sample(conn, _payload())
    transfer = gw.create_transfer(conn, record["id"], _dispatch())

    updated = gw.update_transfer(
        conn, transfer["id"], {"to_team": "microbiology"}
    )
    assert updated["to_team"] == "microbiology"

    assert gw.delete_transfer(conn, transfer["id"]) is True
    assert gw.list_transfers(conn, record["id"])[0]["kind"] == "retention"


# --- reverse links (Batches page) ------------------------------------------

def test_reverse_link_helpers(conn) -> None:
    gw.create_sample(conn, _payload(sample_code="AAA", batch_id=12))
    second = gw.create_sample(
        conn, _payload(sample_code="BBB", batch_id=12)
    )
    gw.create_sample(
        conn,
        _payload(
            sample_code="CCC", origin="benchmark", batch_id=None
        ),
    )
    gw.create_transfer(conn, second["id"], _dispatch())

    assert gw.count_samples_by_batch_id(conn) == {12: 2}
    rows = gw.list_samples_by_batch(conn, 12)
    assert [r["sample_code"] for r in rows] == ["BBB", "AAA"]
    assert set(rows[0]) == {
        "id",
        "sample_code",
        "origin",
        "status",
        "taken_at",
    }
    assert gw.list_samples_by_batch(conn, 999) == []

    counts = gw.transfer_counts_by_sample_id(conn)
    assert counts[second["id"]] == {"total": 2, "dispatches": 1}


def test_validate_sample_summary() -> None:
    good = {
        "id": 1,
        "sample_code": "4A8",
        "origin": "batch",
        "status": "active",
        "taken_at": "2026-09-15",
    }
    assert gw.validate_sample_summary(good) == []

    bad = {"id": "x", "sample_code": "", "origin": None, "status": None}
    problems = gw.validate_sample_summary(bad)
    assert any("missing fields" in p for p in problems)
    assert any("id" in p for p in problems)
    assert any("sample_code" in p for p in problems)
