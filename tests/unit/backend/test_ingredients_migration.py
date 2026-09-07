"""Unit tests for the TEMP legacy custom-field migration helpers.

Layer: unit — backend domain logic (docs/TEST_STRATEGIES.md §4.1). These
helpers exist only to migrate databases written before the custom-field
unit column (commit 9e1c865, 2026-09-07); delete with the migration
(frontend/ingredients/README.md §11).
"""
import pytest

from backend.services.ingredients.migration import has_legacy_entries, to_new_shape


def test_current_shape_needs_no_migration() -> None:
    fields = {
        "pH": {"value": "7", "unit": "mg/L"},
        "grade": {"value": "technical"},
    }
    assert has_legacy_entries(fields) is False


def test_empty_mapping_needs_no_migration() -> None:
    assert has_legacy_entries({}) is False


def test_legacy_string_entry_is_detected() -> None:
    assert has_legacy_entries({"pH": "7"}) is True


def test_mixed_shape_is_detected() -> None:
    fields = {"pH": "7", "grade": {"value": "technical"}}
    assert has_legacy_entries(fields) is True


@pytest.mark.parametrize(
    ("legacy_value", "expected"),
    [("7", "7"), (7, "7"), (True, "True"), (None, "")],
)
def test_to_new_shape_wraps_legacy_entries(legacy_value, expected) -> None:
    assert to_new_shape({"pH": legacy_value}) == {
        "pH": {"value": expected, "unit": ""}
    }


def test_to_new_shape_keeps_current_entries_untouched() -> None:
    fields = {"pH": {"value": "7", "unit": "mg/L"}}
    assert to_new_shape(fields) == fields


def test_to_new_shape_mixed_mapping() -> None:
    out = to_new_shape({"grade": "tech", "pH": {"value": "7", "unit": "mg/L"}})
    assert out == {
        "grade": {"value": "tech", "unit": ""},
        "pH": {"value": "7", "unit": "mg/L"},
    }


def test_to_new_shape_is_idempotent() -> None:
    once = to_new_shape({"pH": "7"})
    assert to_new_shape(once) == once


def test_to_new_shape_empty_mapping() -> None:
    assert to_new_shape({}) == {}
