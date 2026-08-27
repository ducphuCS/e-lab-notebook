"""Unit tests for formula validation.

Layer: unit — backend (docs/TEST_STRATEGIES.md §4.1).
"""
from backend.services.formulas.validation import validate_formula


def _formula(**overrides) -> dict:
    data = {
        "name": "Emulsion X",
        "status": "draft",
        "tags": [],
        "custom_fields": {},
        "composition": [],
        "params": [],
        "procedure": [],
    }
    data.update(overrides)
    return data


def test_valid_minimal_passes() -> None:
    assert validate_formula(_formula()) == []


def test_name_required() -> None:
    problems = validate_formula(_formula(name="  "))
    assert any("name" in p for p in problems)


def test_status_must_be_enum() -> None:
    problems = validate_formula(_formula(status="gaseous"))
    assert any("status" in p for p in problems)


def test_optional_string_fields() -> None:
    problems = validate_formula(_formula(project=123))
    assert any("project" in p for p in problems)


def test_tags_must_be_strings() -> None:
    problems = validate_formula(_formula(tags=["ok", 3]))
    assert any("tags" in p for p in problems)


def test_custom_fields_values_must_be_strings() -> None:
    problems = validate_formula(_formula(custom_fields={"pH": 7}))
    assert any("custom_fields" in p for p in problems)


def test_composition_valid_row_passes() -> None:
    composition = [
        {
            "no": 1,
            "ingredient_id": 5,
            "ingredient_name": "Water",
            "role": "solvent",
            "amount": 50.0,
            "uom": "g",
            "notes": None,
        }
    ]
    assert validate_formula(_formula(composition=composition)) == []


def test_composition_row_validation() -> None:
    composition = [
        {
            "no": "x",
            "ingredient_id": "x",
            "ingredient_name": "",
            "amount": -1,
            "role": 3,
        }
    ]
    problems = validate_formula(_formula(composition=composition))
    assert any("no" in p for p in problems)
    assert any("ingredient_id" in p for p in problems)
    assert any("ingredient_name" in p for p in problems)
    assert any("amount" in p for p in problems)
    assert any("role" in p for p in problems)


def test_composition_must_be_list() -> None:
    problems = validate_formula(_formula(composition={"no": 1}))
    assert any("composition" in p for p in problems)


def test_params_aggregation_enum() -> None:
    params = [{"parameter": "brix", "aggregation": "multiply"}]
    problems = validate_formula(_formula(params=params))
    assert any("aggregation" in p for p in problems)


def test_params_parameter_required() -> None:
    params = [{"parameter": ""}]
    problems = validate_formula(_formula(params=params))
    assert any("parameter" in p for p in problems)


def test_procedure_step_validation() -> None:
    procedure = [
        {
            "name": "",
            "ingredients": [{"ingredient_id": "x", "ingredient_name": "Water"}],
            "params": [{"name": "", "value": 100}],
        }
    ]
    problems = validate_formula(_formula(procedure=procedure))
    assert any("name" in p for p in problems)
    assert any("ingredient_id" in p for p in problems)
    assert any("params" in p for p in problems)


def test_procedure_valid_step_passes() -> None:
    procedure = [
        {
            "name": "Mix",
            "ingredients": [{"ingredient_id": 1, "ingredient_name": "Water"}],
            "equipment": "Blender",
            "duration": "5 min",
            "params": [
                {"name": "speed", "value": "1000", "unit": "rpm"},
                {"name": "temp", "value": "70", "unit": "°C"},
            ],
        }
    ]
    assert validate_formula(_formula(procedure=procedure)) == []
