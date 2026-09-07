"""Unit tests for the ingredients service validation.

Layer: unit — backend domain logic (docs/TEST_STRATEGIES.md §4.1).
"""
from backend.services.ingredients.schema import INGREDIENT_STATES
from backend.services.ingredients.validation import validate_ingredient


def test_valid_record_passes() -> None:
    assert validate_ingredient({"name": "Water", "state": "liquid"}) == []


def test_missing_name_is_reported() -> None:
    problems = validate_ingredient({"state": "liquid"})
    assert any("name" in p for p in problems)


def test_blank_name_is_reported() -> None:
    problems = validate_ingredient({"name": "   "})
    assert any("name" in p for p in problems)


def test_non_string_name_is_reported() -> None:
    problems = validate_ingredient({"name": 42})
    assert any("name" in p for p in problems)


def test_bad_state_is_reported() -> None:
    problems = validate_ingredient({"name": "X", "state": "gaseous"})
    assert any("state" in p for p in problems)


def test_all_known_states_are_accepted() -> None:
    for state in INGREDIENT_STATES:
        assert validate_ingredient({"name": "X", "state": state}) == []


def test_non_string_optional_field_is_reported() -> None:
    problems = validate_ingredient({"name": "X", "uom": 5})
    assert any("uom" in p for p in problems)


def test_custom_fields_must_be_a_dict() -> None:
    problems = validate_ingredient({"name": "X", "custom_fields": ["a"]})
    assert any("custom_fields" in p for p in problems)


def test_custom_fields_blank_key_is_reported() -> None:
    problems = validate_ingredient(
        {"name": "X", "custom_fields": {"": {"value": "v"}}}
    )
    assert any("custom_fields" in p for p in problems)


def test_custom_fields_legacy_string_entry_is_rejected() -> None:
    # v0 stored plain strings ({"pH": "7"}); only the new
    # {key: {value, unit}} shape is accepted now (owner request 2026-09-07).
    problems = validate_ingredient({"name": "X", "custom_fields": {"pH": "7"}})
    assert any("custom_fields" in p for p in problems)


def test_custom_fields_missing_value_is_reported() -> None:
    problems = validate_ingredient(
        {"name": "X", "custom_fields": {"pH": {"unit": "mg/L"}}}
    )
    assert any("value" in p for p in problems)


def test_custom_fields_non_string_value_is_reported() -> None:
    problems = validate_ingredient(
        {"name": "X", "custom_fields": {"pH": {"value": 7}}}
    )
    assert any("value" in p for p in problems)


def test_custom_fields_non_string_unit_is_reported() -> None:
    problems = validate_ingredient(
        {"name": "X", "custom_fields": {"pH": {"value": "7", "unit": 5}}}
    )
    assert any("unit" in p for p in problems)


def test_custom_fields_valid_passes() -> None:
    assert validate_ingredient(
        {
            "name": "X",
            "custom_fields": {
                "pH": {"value": "7", "unit": "mg/L"},
                "grade": {"value": "technical"},
            },
        }
    ) == []
