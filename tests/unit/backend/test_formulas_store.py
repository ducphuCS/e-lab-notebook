"""Unit tests for the SQLite formula store.

Layer: unit — backend (docs/TEST_STRATEGIES.md §4.1). Uses an in-memory
database; no files, no network.
"""
import pytest

from backend.services.formulas import store


@pytest.fixture()
def conn():
    connection = store.connect()  # in-memory
    yield connection
    connection.close()


def _payload(**overrides) -> dict:
    data = {
        "name": "Emulsion X",
        "status": "draft",
        "composition": [
            {
                "no": 1,
                "ingredient_id": 1,
                "ingredient_name": "Water",
                "role": "solvent",
                "amount": 90.0,
                "uom": "g",
                "notes": None,
            }
        ],
        "procedure": [
            {
                "name": "Mix",
                "ingredients": [],
                "equipment": None,
                "duration": None,
                "params": {},
            }
        ],
    }
    data.update(overrides)
    return data


def _changed_composition(amount: float = 95.0) -> list[dict]:
    return [
        {
            "no": 1,
            "ingredient_id": 1,
            "ingredient_name": "Water",
            "role": "solvent",
            "amount": amount,
            "uom": "g",
            "notes": None,
        }
    ]


def test_list_is_empty_initially(conn) -> None:
    assert store.list_formulas(conn) == []


def test_list_orders_by_name(conn) -> None:
    store.create_formula(conn, _payload(name="Zulu"))
    store.create_formula(conn, _payload(name="Alpha"))
    assert [r["name"] for r in store.list_formulas(conn)] == ["Alpha", "Zulu"]


def test_create_returns_id_and_roundtrips(conn) -> None:
    new_id = store.create_formula(conn, _payload())
    record = store.get_formula(conn, new_id)
    assert record["id"] == new_id
    assert record["name"] == "Emulsion X"
    assert record["status"] == "draft"
    assert record["version"] == 1
    assert record["composition"][0]["ingredient_name"] == "Water"
    assert record["tags"] == []
    assert record["custom_fields"] == {}
    assert record["created_at"] and record["updated_at"]


def test_get_missing_returns_none(conn) -> None:
    assert store.get_formula(conn, 999) is None


def test_create_records_version_1_snapshot(conn) -> None:
    new_id = store.create_formula(conn, _payload())
    versions = store.list_formula_versions(conn, new_id)
    assert len(versions) == 1
    assert versions[0]["version"] == 1
    assert versions[0]["snapshot"]["name"] == "Emulsion X"
    assert versions[0]["snapshot"]["composition"][0]["amount"] == 90.0


def test_update_keeps_version_when_composition_unchanged(conn) -> None:
    new_id = store.create_formula(conn, _payload())
    store.update_formula(conn, new_id, {"name": "Emulsion X v2", "status": "active"})
    record = store.get_formula(conn, new_id)
    assert record["name"] == "Emulsion X v2"
    assert record["status"] == "active"
    assert record["version"] == 1  # name/status-only change: no new version
    assert len(store.list_formula_versions(conn, new_id)) == 1


def test_update_bumps_version_when_composition_changes(conn) -> None:
    new_id = store.create_formula(conn, _payload())
    store.update_formula(conn, new_id, {"composition": _changed_composition(95.0)})
    record = store.get_formula(conn, new_id)
    assert record["version"] == 2
    versions = store.list_formula_versions(conn, new_id)
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[1]["snapshot"]["composition"][0]["amount"] == 95.0
    assert versions[1]["snapshot"]["name"] == "Emulsion X"


def test_update_merges_partial_payload(conn) -> None:
    new_id = store.create_formula(conn, _payload())
    store.update_formula(conn, new_id, {"owner": "ducphu"})
    record = store.get_formula(conn, new_id)
    assert record["owner"] == "ducphu"
    assert record["status"] == "draft"  # untouched field kept


def test_update_missing_returns_false(conn) -> None:
    assert store.update_formula(conn, 999, {"name": "X"}) is False


def test_delete_removes_formula_and_versions(conn) -> None:
    new_id = store.create_formula(conn, _payload())
    store.update_formula(conn, new_id, {"composition": _changed_composition(95.0)})
    assert store.delete_formula(conn, new_id) is True
    assert store.get_formula(conn, new_id) is None
    assert store.list_formula_versions(conn, new_id) == []


def test_delete_missing_returns_false(conn) -> None:
    assert store.delete_formula(conn, 999) is False


def test_duplicate_copies_content_with_new_id_and_version_1(conn) -> None:
    source_id = store.create_formula(conn, _payload(name="Original", status="approved"))
    new_id = store.duplicate_formula(conn, source_id)
    assert new_id != source_id
    source = store.get_formula(conn, source_id)
    dup = store.get_formula(conn, new_id)
    assert dup["name"] == "Copy of Original"
    assert dup["status"] == "approved"
    assert dup["composition"] == source["composition"]
    assert dup["procedure"] == source["procedure"]
    assert dup["version"] == 1
    assert len(store.list_formula_versions(conn, new_id)) == 1
    assert len(store.list_formula_versions(conn, source_id)) == 1


def test_duplicate_with_custom_name(conn) -> None:
    source_id = store.create_formula(conn, _payload())
    new_id = store.duplicate_formula(conn, source_id, "Trial 2")
    assert store.get_formula(conn, new_id)["name"] == "Trial 2"


def test_duplicate_missing_returns_none(conn) -> None:
    assert store.duplicate_formula(conn, 999) is None


def test_get_formula_version(conn) -> None:
    new_id = store.create_formula(conn, _payload())
    store.update_formula(conn, new_id, {"composition": _changed_composition(95.0)})
    v1 = store.get_formula_version(conn, new_id, 1)
    v2 = store.get_formula_version(conn, new_id, 2)
    assert v1["snapshot"]["composition"][0]["amount"] == 90.0
    assert v2["snapshot"]["composition"][0]["amount"] == 95.0
    assert store.get_formula_version(conn, new_id, 99) is None
