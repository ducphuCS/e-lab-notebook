"""Unit tests for the Ingredients page utilities.

Layer: unit — frontend (docs/TEST_STRATEGIES.md §4.2). Pure helpers only;
no streamlit, no I/O.
"""
import pandas as pd

from frontend.ingredients.utils import (
    CUSTOM_FIELD_COLUMNS,
    build_ingredient_payload,
    custom_fields_from_df,
    custom_fields_to_df,
)


def test_custom_fields_columns_are_key_value_unit() -> None:
    assert CUSTOM_FIELD_COLUMNS == ("key", "value", "unit")


def test_custom_fields_to_df_builds_key_value_unit_rows() -> None:
    df = custom_fields_to_df(
        {"pH": {"value": "7", "unit": "mg/L"}, "grade": {"value": "technical"}}
    )
    assert list(df.columns) == ["key", "value", "unit"]
    rows = df.values.tolist()
    assert ["pH", "7", "mg/L"] in rows
    assert ["grade", "technical", ""] in rows


def test_custom_fields_to_df_handles_empty_and_none() -> None:
    assert custom_fields_to_df(None).empty
    assert custom_fields_to_df({}).empty


def test_custom_fields_roundtrip_preserves_value_and_unit() -> None:
    fields = {
        "pH": {"value": "7", "unit": "mg/L"},
        "grade": {"value": "technical", "unit": ""},
    }
    assert custom_fields_from_df(custom_fields_to_df(fields)) == fields


def test_custom_fields_from_df_normalizes_missing_unit_to_empty() -> None:
    df = pd.DataFrame({"key": ["grade"], "value": ["technical"], "unit": [""]})
    # Stored entries always carry both keys ({value, unit}).
    assert custom_fields_from_df(df) == {
        "grade": {"value": "technical", "unit": ""}
    }


def test_custom_fields_from_df_drops_blank_keys_and_keeps_empty_unit() -> None:
    df = pd.DataFrame(
        {
            "key": ["grade", "   ", None],
            "value": ["technical", "x", "y"],
            "unit": ["", "kg", "L"],
        }
    )
    assert custom_fields_from_df(df) == {
        "grade": {"value": "technical", "unit": ""}
    }


def test_build_ingredient_payload_passes_custom_fields_through() -> None:
    payload = build_ingredient_payload(
        name="Water",
        custom_fields={"pH": {"value": "7", "unit": "mg/L"}},
    )
    assert payload["custom_fields"] == {"pH": {"value": "7", "unit": "mg/L"}}
