"""Unit tests for the batches gateway client (policy guards).

Layer: unit — gateway (docs/TEST_STRATEGIES.md §4.1/§6): the gateway is
headless (no streamlit) and calls the store in-process. Covers the policy
guards from README Q1/Q6 — immutability of identity fields, the plan
freeze once the batch has left 'planned', and the delete-only-while-
'planned' rule — plus validation propagation.
"""
import pytest

from backend.gateway import batches as gw


@pytest.fixture()
def conn():
    connection = gw.connect()  # in-memory
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
    }
    data.update(overrides)
    return data


def test_create_valid_returns_record(conn) -> None:
    record = gw.create_batch(conn, _payload())
    assert record["batch_code"] == "B-0001"
    assert record["status"] == "planned"
    assert record["id"] == 1


def test_create_invalid_payload_raises(conn) -> None:
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.create_batch(conn, _payload(name="  "))
    assert any("name" in p for p in excinfo.value.problems)


def test_update_not_found_raises(conn) -> None:
    with pytest.raises(gw.GatewayError):
        gw.update_batch(conn, 999, {"name": "X"})


def test_identity_fields_are_immutable(conn) -> None:
    record = gw.create_batch(conn, _payload())
    for field, value in [
        ("batch_code", "B-9999"),
        ("formula_id", 42),
        ("formula_name", "Other"),
        ("formula_version", 99),
    ]:
        with pytest.raises(gw.GatewayError) as excinfo:
            gw.update_batch(conn, record["id"], {field: value})
        assert any("cannot be changed after creation" in p for p in excinfo.value.problems)


def test_identity_field_equal_value_passes(conn) -> None:
    """Re-sending the same immutable value (e.g. a full-record echo) is fine."""
    record = gw.create_batch(conn, _payload())
    updated = gw.update_batch(
        conn, record["id"], {"formula_version": record["formula_version"]}
    )
    assert updated["formula_version"] == record["formula_version"]


def test_planned_editable_while_planned(conn) -> None:
    record = gw.create_batch(conn, _payload())
    new_planned = _planned(amount=2000.0)
    updated = gw.update_batch(conn, record["id"], {"planned": new_planned})
    assert updated["planned"]["composition"][0]["amount"] == 2000.0


def test_planned_frozen_once_batch_left_planned(conn) -> None:
    record = gw.create_batch(conn, _payload())
    gw.update_batch(conn, record["id"], {"status": "in progress"})
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.update_batch(conn, record["id"], {"planned": _planned(amount=1.0)})
    assert any("planned" in p for p in excinfo.value.problems)

    # ...but a header/actuals update still works on a completed batch
    gw.update_batch(conn, record["id"], {"status": "completed"})
    updated = gw.update_batch(
        conn,
        record["id"],
        {"actual": {"observations": "Done."}},
    )
    assert updated["actual"]["observations"] == "Done."
    assert updated["status"] == "completed"


def test_actual_updates_merge_with_existing_actual(conn) -> None:
    record = gw.create_batch(conn, _payload())
    gw.update_batch(
        conn,
        record["id"],
        {"actual": {"composition": [{"no": 1, "amount": 2240.0, "uom": "g"}]}},
    )
    record = gw.update_batch(
        conn, record["id"], {"actual": {"yield": {"amount": 2480.0, "uom": "g"}}}
    )
    # the page-level merge sends the full actual object each time
    assert record["actual"]["composition"][0]["amount"] == 2240.0
    assert record["actual"]["yield"] == {"amount": 2480.0, "uom": "g"}


def test_delete_only_while_planned(conn) -> None:
    record = gw.create_batch(conn, _payload())
    assert gw.delete_batch(conn, record["id"]) is True
    assert gw.get_batch(conn, record["id"]) is None


def test_delete_blocked_after_planned(conn) -> None:
    record = gw.create_batch(conn, _payload())
    gw.update_batch(conn, record["id"], {"status": "in progress"})
    with pytest.raises(gw.GatewayError) as excinfo:
        gw.delete_batch(conn, record["id"])
    assert any("planned" in p for p in excinfo.value.problems)

    gw.update_batch(conn, record["id"], {"status": "completed"})
    with pytest.raises(gw.GatewayError):
        gw.delete_batch(conn, record["id"])


def test_delete_not_found_raises(conn) -> None:
    with pytest.raises(gw.GatewayError):
        gw.delete_batch(conn, 999)


def test_list_and_get_roundtrip(conn) -> None:
    first = gw.create_batch(conn, _payload(name="A"))
    second = gw.create_batch(conn, _payload(name="B"))
    assert [r["id"] for r in gw.list_batches(conn)] == [second["id"], first["id"]]
    assert gw.get_batch(conn, second["id"])["batch_code"] == "B-0002"
    assert gw.get_batch(conn, 999) is None


def test_reverse_link_helpers(conn) -> None:
    gw.create_batch(conn, _payload(formula_id=1, name="A"))
    gw.create_batch(conn, _payload(formula_id=1, name="B"))
    gw.create_batch(conn, _payload(formula_id=2, name="C"))

    assert gw.count_batches_by_formula_id(conn) == {1: 2, 2: 1}
    rows = gw.list_batches_by_formula(conn, 1)
    assert [r["name"] for r in rows] == ["B", "A"]
    assert all(r["formula_version"] == 3 for r in rows)
    assert gw.list_batches_by_formula(conn, 999) == []


def test_validate_batch_summary() -> None:
    good = {
        "id": 1,
        "batch_code": "B-0001",
        "name": "Run",
        "formula_version": 3,
        "status": "planned",
        "updated_at": "2026-09-03T10:00:00+00:00",
    }
    assert gw.validate_batch_summary(good) == []

    bad = {
        "id": "x",
        "batch_code": "",
        "name": None,
        "formula_version": "three",
        "status": None,
    }
    problems = gw.validate_batch_summary(bad)
    assert any("missing fields" in p for p in problems)
    assert any("id" in p for p in problems)
    assert any("batch_code" in p for p in problems)
    assert any("formula_version" in p for p in problems)
