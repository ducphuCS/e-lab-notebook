"""Pure helpers for the Ingredients page (no streamlit).

Extracted so they are unit-testable without a UI runtime
(docs/TEST_STRATEGIES.md §4.2). Mirrors the frontend.doe.validators
pattern: page files stay thin glue.
"""
from __future__ import annotations

import pandas as pd

CUSTOM_FIELD_COLUMNS = ("key", "value", "unit")


def _cell_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def custom_fields_to_df(
    custom_fields: dict[str, dict[str, str]] | None,
) -> pd.DataFrame:
    """Stored mapping (name -> {value, unit}) to the editor DataFrame.

    Only the current shape is expected; legacy plain-string entries are
    rejected at the gateway before they reach the page.
    """
    items = [
        (key, entry["value"], entry.get("unit", ""))
        for key, entry in (custom_fields or {}).items()
    ]
    return pd.DataFrame(items, columns=CUSTOM_FIELD_COLUMNS)


def custom_fields_from_df(df: pd.DataFrame | None) -> dict[str, dict[str, str]]:
    """Editor DataFrame to the stored mapping; blank keys are dropped."""
    result: dict[str, dict[str, str]] = {}
    if df is None or df.empty:
        return result
    for _, row in df.iterrows():
        key = _cell_text(row.get("key")).strip()
        if key:
            result[key] = {
                "value": _cell_text(row.get("value")),
                "unit": _cell_text(row.get("unit")),
            }
    return result


def formula_usage_block_reason(formula_count: int | None) -> str | None:
    """Why an ingredient cannot be deleted, or None when deletion is
    allowed (README §6).

    Ingredients referenced by at least one formula are protected: formula
    composition rows keep the ingredient id. Mirrors
    ``frontend/formulas/utils.delete_block_reason`` — the condition lives
    in another service, so the guard is enforced in the delete confirm
    and the store delete itself stays unconditional.
    """
    count = formula_count or 0
    if count <= 0:
        return None
    noun = "formula" if count == 1 else "formulas"
    return f"{count} {noun} use this ingredient."


def build_ingredient_payload(
    name: str,
    item_code: str = "",
    item_description: str = "",
    supplier: str = "",
    notes: str = "",
    uom: str = "",
    state: str | None = None,
    custom_fields: dict[str, dict[str, str]] | None = None,
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
