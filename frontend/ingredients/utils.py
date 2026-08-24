"""Pure helpers for the Ingredients page (no streamlit).

Extracted so they are unit-testable without a UI runtime
(docs/TEST_STRATEGIES.md §4.2). Mirrors the frontend.doe.validators
pattern: page files stay thin glue.
"""
from __future__ import annotations

import pandas as pd

CUSTOM_FIELD_COLUMNS = ("key", "value")


def _cell_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def custom_fields_to_df(custom_fields: dict[str, str] | None) -> pd.DataFrame:
    """dict of name -> value to the key/value editor DataFrame."""
    items = [(key, value) for key, value in (custom_fields or {}).items()]
    return pd.DataFrame(items, columns=CUSTOM_FIELD_COLUMNS)


def custom_fields_from_df(df: pd.DataFrame | None) -> dict[str, str]:
    """Editor DataFrame to dict; rows with blank keys are dropped."""
    result: dict[str, str] = {}
    if df is None or df.empty:
        return result
    for _, row in df.iterrows():
        key = _cell_text(row.get("key")).strip()
        value = _cell_text(row.get("value"))
        if key:
            result[key] = value
    return result


def build_ingredient_payload(
    name: str,
    item_code: str = "",
    item_description: str = "",
    supplier: str = "",
    notes: str = "",
    uom: str = "",
    state: str | None = None,
    custom_fields: dict[str, str] | None = None,
) -> dict:
    """Build a service payload from form values (blank strings -> None)."""
    return {
        "name": name.strip(),
        "item_code": item_code.strip() or None,
        "item_description": item_description.strip() or None,
        "supplier": supplier.strip() or None,
        "notes": notes.strip() or None,
        "uom": uom.strip() or None,
        "state": state,
        "custom_fields": custom_fields or {},
    }
