"""Unit tests for batch validation.

Layer: unit — backend (docs/TEST_STRATEGIES.md §4.1).
"""
from backend.services.batches.validation import validate_batch


def _row(**overrides) -> dict:
    data = {
        "no": 1,
        "ingredient_id": 7,
        "ingredient_name": "Water",
        "amount": 2250.0,
        "uom": "g",
        "notes": None,
    }
    data.update(overrides)
    return data


def _planned(**overrides) -> dict:
    data = {
        "target_yield": {"amount": 2500.0, "uom": "g"},
        "composition": [_row()],
        "processing": [],
    }
    data.update(overrides)
    return data


def _batch(**overrides) -> dict:
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


def test_valid_minimal_passes() -> None:
    assert validate_batch(_batch()) == []


def test_name_required() -> None:
    problems = validate_batch(_batch(name="  "))
    assert any("name" in p for p in problems)


def test_status_must_be_enum() -> None:
    problems = validate_batch(_batch(status="gaseous"))
    assert any("status" in p for p in problems)
    # a missing status is also rejected (the store default is not applied
    # until create, and validation runs on the payload first)
    problems = validate_batch(_batch(status=None))
    assert any("status" in p for p in problems)


def test_formula_reference_required() -> None:
    problems = validate_batch(_batch(formula_id=None))
    assert any("formula_id" in p for p in problems)
    problems = validate_batch(_batch(formula_name="  "))
    assert any("formula_name" in p for p in problems)
    problems = validate_batch(_batch(formula_version=0))
    assert any("formula_version" in p for p in problems)
    problems = validate_batch(_batch(formula_version="x"))
    assert any("formula_version" in p for p in problems)


def test_owner_must_be_string() -> None:
    problems = validate_batch(_batch(owner=3))
    assert any("owner" in p for p in problems)


def test_planned_required_dict() -> None:
    problems = validate_batch(_batch(planned=None))
    assert any("planned" in p for p in problems)
    problems = validate_batch(_batch(planned="not a dict"))
    assert any("planned" in p for p in problems)


def test_planned_target_yield_validation() -> None:
    planned = _planned(target_yield={"amount": -5, "uom": "g"})
    problems = validate_batch(_batch(planned=planned))
    assert any("target_yield" in p for p in problems)

    planned = _planned(target_yield="100 g")
    problems = validate_batch(_batch(planned=planned))
    assert any("target_yield" in p for p in problems)


def test_planned_composition_must_be_non_empty() -> None:
    problems = validate_batch(_batch(planned=_planned(composition=[])))
    assert any("composition" in p for p in problems)


def test_planned_composition_row_validation() -> None:
    planned = _planned(
        composition=[
            {
                "no": "x",
                "ingredient_id": "x",
                "ingredient_name": "",
                "amount": -1,
                "uom": 3,
            }
        ]
    )
    problems = validate_batch(_batch(planned=planned))
    assert any("no" in p for p in problems)
    assert any("ingredient_id" in p for p in problems)
    assert any("ingredient_name" in p for p in problems)
    assert any("amount" in p for p in problems)
    assert any("uom" in p for p in problems)


def test_planned_processing_snapshot_validation() -> None:
    # a valid formula-procedure snapshot passes
    planned = _planned(
        processing=[
            {
                "name": "Mix",
                "ingredients": [
                    {"ingredient_id": 7, "ingredient_name": "Water"}
                ],
                "equipment": "Blender",
                "duration": "5 min",
                "params": [{"name": "speed", "value": "1000", "unit": "rpm"}],
            }
        ]
    )
    assert validate_batch(_batch(planned=planned)) == []

    # malformed snapshot is rejected
    planned = _planned(processing=[{"name": "", "params": [{"name": ""}]}])
    problems = validate_batch(_batch(planned=planned))
    assert any("name" in p for p in problems)


def test_actual_optional_and_lenient() -> None:
    assert validate_batch(_batch(actual=None)) == []
    assert validate_batch(_batch(actual={})) == []
    assert validate_batch(_batch(actual="oops")) != []


def test_actual_composition_row_type_checks() -> None:
    actual = {"composition": [{"no": "x", "amount": -3, "note": 5}]}
    problems = validate_batch(_batch(actual=actual))
    assert any("no" in p for p in problems)
    assert any("amount" in p for p in problems)
    assert any("note" in p for p in problems)

    # partially recorded rows are fine
    actual = {"composition": [{"no": 1}]}
    assert validate_batch(_batch(actual=actual)) == []


def test_actual_yield_and_observations() -> None:
    actual = {"yield": {"amount": -1, "uom": 3}, "observations": 4}
    problems = validate_batch(_batch(actual=actual))
    assert any("yield" in p for p in problems)
    assert any("observations" in p for p in problems)

    actual = {"yield": {"amount": 2480.0, "uom": "g"}, "observations": "Fine."}
    assert validate_batch(_batch(actual=actual)) == []
