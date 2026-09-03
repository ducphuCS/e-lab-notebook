"""Unit tests for the SQLite batch store.

Layer: unit — backend (docs/TEST_STRATEGIES.md §4.1). Uses an in-memory
database; no files, no network.
"""
import pytest

from backend.services.batches import store


@pytest.fixture()
def conn():
    connection = store.connect()  # in-memory
    yield connection
    connection.close()


def _planned(amount: float = 2250.0) -> dict:
    return {
        "target_yield": {"amount": 2500.0, "uom": "g"},
        "composition": [
            {
                "no": 1,
                "ingredient_id": 7,
                "ingredient_name": "Water",
                "amount": amount,
                "uom": "g",
                "notes": None,
            }
        ],
        "processing": [],
    }


def _payload(**overrides) -> dict:
    data = {
        "name": "Emulsion 2500g",
        "formula_id": 1,
        "formula_name": "Emulsion X",
        "formula_version": 3,
        "status": "planned",
        "planned": _planned(),
        "actual": {},
        "owner": None,
    }
    data.update(overrides)
    return data


def test_create_assigns_sequential_codes(conn) -> None:
    first = store.create_batch(conn, _payload(name="A"))
    second = store.create_batch(conn, _payload(name="B"))
    assert store.get_batch(conn, first)["batch_code"] == "B-0001"
    assert store.get_batch(conn, second)["batch_code"] == "B-0002"


def test_create_defaults_status_to_planned(conn) -> None:
    batch_id = store.create_batch(conn, _payload())  # no status key
    assert store.get_batch(conn, batch_id)["status"] == "planned"


def test_create_roundtrips_json_fields(conn) -> None:
    actual = {
        "composition": [
            {
                "no": 1,
                "ingredient_id": 7,
                "ingredient_name": "Water",
                "amount": 2240.0,
                "uom": "g",
                "note": "slightly under",
            }
        ],
        "yield": {"amount": 2480.0, "uom": "g"},
        "observations": "Fine.",
    }
    batch_id = store.create_batch(conn, _payload(actual=actual))
    record = store.get_batch(conn, batch_id)
    assert record["planned"]["target_yield"] == {"amount": 2500.0, "uom": "g"}
    assert record["planned"]["composition"][0]["ingredient_name"] == "Water"
    assert record["actual"] == actual


def test_list_orders_newest_first(conn) -> None:
    a = store.create_batch(conn, _payload(name="A"))
    b = store.create_batch(conn, _payload(name="B"))
    rows = store.list_batches(conn)
    assert [r["id"] for r in rows] == [b, a]
    assert [r["name"] for r in rows] == ["B", "A"]


def test_get_missing_returns_none(conn) -> None:
    assert store.get_batch(conn, 999) is None


def test_update_partial_merge(conn) -> None:
    batch_id = store.create_batch(conn, _payload())
    record = store.get_batch(conn, batch_id)

    assert store.update_batch(conn, batch_id, {"name": "Renamed", "owner": "A"})
    updated = store.get_batch(conn, batch_id)
    assert updated["name"] == "Renamed"
    assert updated["owner"] == "A"
    # untouched by the partial update
    assert updated["status"] == "planned"
    assert updated["formula_id"] == 1
    assert updated["formula_version"] == 3
    assert updated["planned"] == record["planned"]
    assert updated["batch_code"] == "B-0001"
    assert updated["created_at"] == record["created_at"]
    assert updated["updated_at"] >= record["created_at"]


def test_update_never_writes_identity_fields(conn) -> None:
    """The store is dumb, but its UPDATE statement is fixed to mutable
    columns — even a slipped key cannot drift identity."""
    batch_id = store.create_batch(conn, _payload())
    store.update_batch(
        conn,
        batch_id,
        {
            "name": "X",
            "batch_code": "B-9999",
            "formula_id": 42,
            "formula_name": "Hacked",
            "formula_version": 99,
        },
    )
    updated = store.get_batch(conn, batch_id)
    assert updated["batch_code"] == "B-0001"
    assert updated["formula_id"] == 1
    assert updated["formula_name"] == "Emulsion X"
    assert updated["formula_version"] == 3


def test_update_missing_returns_false(conn) -> None:
    assert store.update_batch(conn, 999, {"name": "X"}) is False


def test_delete_removes(conn) -> None:
    batch_id = store.create_batch(conn, _payload())
    assert store.delete_batch(conn, batch_id) is True
    assert store.get_batch(conn, batch_id) is None
    assert store.delete_batch(conn, batch_id) is False


def test_deleted_codes_are_not_reused(conn) -> None:
    """The next code comes from the highest existing suffix, so deleting a
    batch never causes a code to be handed out twice."""
    first = store.create_batch(conn, _payload())
    store.delete_batch(conn, first)
    second = store.create_batch(conn, _payload())
    assert store.get_batch(conn, second)["batch_code"] == "B-0002"


def test_batch_code_pads_beyond_nine(conn) -> None:
    for _ in range(10):
        store.create_batch(conn, _payload())
    rows = store.list_batches(conn)
    codes = [r["batch_code"] for r in rows]
    assert "B-0010" in codes


def test_list_batches_by_formula_returns_light_summaries(conn) -> None:
    a = store.create_batch(conn, _payload(formula_id=1, name="A"))
    b = store.create_batch(conn, _payload(formula_id=1, name="B"))
    store.create_batch(conn, _payload(formula_id=2, name="Other"))

    rows = store.list_batches_by_formula(conn, 1)
    assert [r["id"] for r in rows] == [b, a]  # most recent first
    assert set(rows[0]) == {"id", "batch_code", "name", "status", "updated_at"}
    # no JSON payloads in the light summaries
    assert "planned" not in rows[0] and "actual" not in rows[0]
    assert store.list_batches_by_formula(conn, 999) == []


def test_count_batches_by_formula_id_groups(conn) -> None:
    store.create_batch(conn, _payload(formula_id=1, name="A"))
    store.create_batch(conn, _payload(formula_id=1, name="B"))
    store.create_batch(conn, _payload(formula_id=2, name="C"))
    assert store.count_batches_by_formula_id(conn) == {1: 2, 2: 1}


def test_count_batches_by_formula_id_empty(conn) -> None:
    assert store.count_batches_by_formula_id(conn) == {}
