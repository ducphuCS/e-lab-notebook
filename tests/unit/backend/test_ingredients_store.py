"""Unit tests for the SQLite ingredient store.

Layer: unit — backend (docs/TEST_STRATEGIES.md §4.1). Uses an in-memory
database; no files, no network.
"""
import pytest

from backend.services.ingredients import store


@pytest.fixture()
def conn():
    connection = store.connect()  # in-memory
    yield connection
    connection.close()


def test_list_is_empty_initially(conn) -> None:
    assert store.list_ingredients(conn) == []


def test_create_returns_id_and_roundtrips(conn) -> None:
    new_id = store.create_ingredient(conn, {"name": "Water"})
    record = store.get_ingredient(conn, new_id)
    assert record["id"] == new_id
    assert record["name"] == "Water"
    assert record["custom_fields"] == {}


def test_list_orders_by_name(conn) -> None:
    store.create_ingredient(conn, {"name": "Zinc"})
    store.create_ingredient(conn, {"name": "Alum"})
    assert [r["name"] for r in store.list_ingredients(conn)] == ["Alum", "Zinc"]


def test_custom_fields_json_roundtrip(conn) -> None:
    new_id = store.create_ingredient(
        conn,
        {
            "name": "Water",
            "custom_fields": {"pH": {"value": "7", "unit": "mg/L"}},
        },
    )
    assert store.get_ingredient(conn, new_id)["custom_fields"] == {
        "pH": {"value": "7", "unit": "mg/L"}
    }


def test_get_missing_returns_none(conn) -> None:
    assert store.get_ingredient(conn, 999) is None


def test_update_merges_partial_payload(conn) -> None:
    new_id = store.create_ingredient(conn, {"name": "Water", "uom": "L"})
    assert store.update_ingredient(conn, new_id, {"state": "liquid"}) is True
    record = store.get_ingredient(conn, new_id)
    assert record["uom"] == "L"
    assert record["state"] == "liquid"


def test_update_missing_returns_false(conn) -> None:
    assert store.update_ingredient(conn, 999, {"name": "X"}) is False


def test_update_cannot_change_id(conn) -> None:
    new_id = store.create_ingredient(conn, {"name": "Water"})
    store.update_ingredient(conn, new_id, {"id": 999, "name": "X"})
    record = store.get_ingredient(conn, new_id)
    assert record["id"] == new_id
    assert store.get_ingredient(conn, 999) is None


def test_delete_removes_record(conn) -> None:
    new_id = store.create_ingredient(conn, {"name": "Water"})
    assert store.delete_ingredient(conn, new_id) is True
    assert store.get_ingredient(conn, new_id) is None


def test_delete_missing_returns_false(conn) -> None:
    assert store.delete_ingredient(conn, 999) is False
