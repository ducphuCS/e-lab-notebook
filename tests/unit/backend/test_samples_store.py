"""Unit tests for the SQLite sample store.

Layer: unit — backend (docs/TEST_STRATEGIES.md §4.1). Uses an in-memory
database; no files, no network.
"""
import pytest

from backend.services.samples import store


@pytest.fixture()
def conn():
    connection = store.connect()  # in-memory
    yield connection
    connection.close()


def _sample(**overrides) -> dict:
    data = {
        "sample_code": "4A8",
        "origin": "batch",
        "batch_id": 12,
        "source": None,
        "taken_at": "2026-09-15",
        "status": "active",
        "notes": None,
    }
    data.update(overrides)
    return data


def _retention(**overrides) -> dict:
    data = {
        "sent_at": "2026-09-15",
        "storage_condition": "refrigerator",
        "sent_by": None,
        "notes": None,
    }
    data.update(overrides)
    return data


def _create(conn, sample=None, retention=None) -> int:
    return store.create_sample_with_retention(
        conn, sample or _sample(), retention or _retention()
    )


# --- samples ---------------------------------------------------------------

def test_create_sample_with_retention(conn) -> None:
    sample_id = _create(conn)
    record = store.get_sample(conn, sample_id)
    assert record["sample_code"] == "4A8"
    assert record["origin"] == "batch"
    assert record["batch_id"] == 12
    assert record["status"] == "active"
    assert record["created_at"] and record["updated_at"]

    transfers = store.list_transfers(conn, sample_id)
    assert len(transfers) == 1
    assert transfers[0]["kind"] == "retention"
    assert transfers[0]["to_team"] is None
    assert transfers[0]["storage_condition"] == "refrigerator"


def test_retention_sent_at_defaults_to_taken_at(conn) -> None:
    sample_id = _create(conn, retention={"storage_condition": "TA35"})
    transfer = store.list_transfers(conn, sample_id)[0]
    assert transfer["sent_at"] == "2026-09-15"


def test_create_defaults_status_and_origin(conn) -> None:
    sample_id = _create(
        conn, sample=_sample(origin=None, status=None, batch_id=None)
    )
    record = store.get_sample(conn, sample_id)
    assert record["origin"] == "batch"
    assert record["status"] == "active"


def test_benchmark_sample_roundtrips(conn) -> None:
    sample_id = _create(
        conn,
        sample=_sample(origin="benchmark", batch_id=None, source="Brand X"),
    )
    record = store.get_sample(conn, sample_id)
    assert record["origin"] == "benchmark"
    assert record["batch_id"] is None
    assert record["source"] == "Brand X"


def test_sample_code_exists_is_case_insensitive(conn) -> None:
    _create(conn, sample=_sample(sample_code="4A8"))
    assert store.sample_code_exists(conn, "4A8") is True
    assert store.sample_code_exists(conn, "4a8") is True
    assert store.sample_code_exists(conn, "ZZZ") is False


def test_list_samples_newest_first(conn) -> None:
    first = _create(conn, sample=_sample(sample_code="AAA"))
    second = _create(conn, sample=_sample(sample_code="BBB"))
    assert [r["id"] for r in store.list_samples(conn)] == [second, first]


def test_get_missing_returns_none(conn) -> None:
    assert store.get_sample(conn, 999) is None


def test_update_sample_partial_merge(conn) -> None:
    sample_id = _create(conn)
    assert store.update_sample(
        conn, sample_id, {"status": "depleted", "notes": "used up"}
    )
    record = store.get_sample(conn, sample_id)
    assert record["status"] == "depleted"
    assert record["notes"] == "used up"
    # untouched
    assert record["sample_code"] == "4A8"
    assert record["origin"] == "batch"
    assert record["batch_id"] == 12


def test_update_sample_never_writes_identity(conn) -> None:
    """The store is dumb, but its UPDATE statement is fixed to mutable
    columns — even a slipped key cannot drift identity/provenance."""
    sample_id = _create(conn)
    store.update_sample(
        conn,
        sample_id,
        {
            "status": "expired",
            "sample_code": "ZZZ",
            "origin": "benchmark",
            "batch_id": 99,
        },
    )
    record = store.get_sample(conn, sample_id)
    assert record["sample_code"] == "4A8"
    assert record["origin"] == "batch"
    assert record["batch_id"] == 12


def test_update_missing_returns_false(conn) -> None:
    assert store.update_sample(conn, 999, {"status": "expired"}) is False


def test_delete_sample_removes_it_and_its_transfers(conn) -> None:
    sample_id = _create(conn)
    store.create_transfer(
        conn,
        sample_id,
        {
            "kind": "dispatch",
            "to_team": "shelf-life",
            "sent_at": "2026-10-01",
            "storage_condition": "TA45",
        },
    )
    assert store.delete_sample(conn, sample_id) is True
    assert store.get_sample(conn, sample_id) is None
    assert store.list_transfers(conn, sample_id) == []
    assert store.delete_sample(conn, sample_id) is False


# --- transfers -------------------------------------------------------------

def test_transfer_crud(conn) -> None:
    sample_id = _create(conn)
    transfer_id = store.create_transfer(
        conn,
        sample_id,
        {
            "kind": "dispatch",
            "to_team": "microbiology",
            "sent_at": "2026-10-01",
            "storage_condition": "TA35",
            "sent_by": "ducphu",
            "notes": "for culture",
        },
    )
    transfer = store.get_transfer(conn, transfer_id)
    assert transfer["to_team"] == "microbiology"
    assert transfer["storage_condition"] == "TA35"

    assert store.update_transfer(
        conn, transfer_id, {"to_team": "shelf-life"}
    )
    assert store.get_transfer(conn, transfer_id)["to_team"] == "shelf-life"

    assert store.delete_transfer(conn, transfer_id)
    assert store.get_transfer(conn, transfer_id) is None
    assert store.delete_transfer(conn, transfer_id) is False


def test_update_transfer_never_rewrites_kind(conn) -> None:
    sample_id = _create(conn)
    transfer_id = store.create_transfer(
        conn,
        sample_id,
        {
            "kind": "dispatch",
            "to_team": "shelf-life",
            "sent_at": "2026-10-01",
            "storage_condition": "TA45",
        },
    )
    store.update_transfer(conn, transfer_id, {"kind": "retention"})
    assert store.get_transfer(conn, transfer_id)["kind"] == "dispatch"


def test_list_transfers_newest_first(conn) -> None:
    sample_id = _create(conn, retention=_retention(sent_at="2026-09-15"))
    store.create_transfer(
        conn,
        sample_id,
        {
            "kind": "dispatch",
            "to_team": "shelf-life",
            "sent_at": "2026-10-01",
            "storage_condition": "TA45",
        },
    )
    kinds = [t["kind"] for t in store.list_transfers(conn, sample_id)]
    assert kinds == ["dispatch", "retention"]


def test_count_transfers_by_kind(conn) -> None:
    sample_id = _create(conn)
    assert store.count_transfers(conn, sample_id) == 1
    assert store.count_transfers(conn, sample_id, kind="retention") == 1
    assert store.count_transfers(conn, sample_id, kind="dispatch") == 0
    store.create_transfer(
        conn,
        sample_id,
        {
            "kind": "dispatch",
            "to_team": "shelf-life",
            "sent_at": "2026-10-01",
            "storage_condition": "TA45",
        },
    )
    assert store.count_transfers(conn, sample_id) == 2
    assert store.count_transfers(conn, sample_id, kind="dispatch") == 1


# --- reverse links (Batches page) ------------------------------------------

def test_list_samples_by_batch_returns_light_summaries(conn) -> None:
    first = _create(conn, sample=_sample(sample_code="AAA", batch_id=12))
    second = _create(conn, sample=_sample(sample_code="BBB", batch_id=12))
    _create(
        conn,
        sample=_sample(sample_code="CCC", origin="benchmark", batch_id=None),
    )

    rows = store.list_samples_by_batch(conn, 12)
    assert [r["id"] for r in rows] == [second, first]  # most recent first
    assert set(rows[0]) == {
        "id",
        "sample_code",
        "origin",
        "status",
        "taken_at",
    }
    assert store.list_samples_by_batch(conn, 999) == []


def test_count_samples_by_batch_id_groups(conn) -> None:
    _create(conn, sample=_sample(sample_code="AAA", batch_id=12))
    _create(conn, sample=_sample(sample_code="BBB", batch_id=12))
    _create(conn, sample=_sample(sample_code="CCC", batch_id=13))
    _create(
        conn,
        sample=_sample(sample_code="DDD", origin="benchmark", batch_id=None),
    )
    assert store.count_samples_by_batch_id(conn) == {12: 2, 13: 1}


def test_count_samples_by_batch_id_empty(conn) -> None:
    assert store.count_samples_by_batch_id(conn) == {}


def test_transfer_counts_by_sample_id(conn) -> None:
    sample_id = _create(conn)
    store.create_transfer(
        conn,
        sample_id,
        {
            "kind": "dispatch",
            "to_team": "shelf-life",
            "sent_at": "2026-10-01",
            "storage_condition": "TA45",
        },
    )
    counts = store.transfer_counts_by_sample_id(conn)
    assert counts[sample_id] == {"total": 2, "dispatches": 1}


def test_transfer_counts_empty(conn) -> None:
    assert store.transfer_counts_by_sample_id(conn) == {}
