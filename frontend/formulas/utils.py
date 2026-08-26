"""Pure helpers for the Formulas pages (no streamlit).

Extracted so they are unit-testable without a UI runtime
(docs/TEST_STRATEGIES.md §4.2). Mirrors the frontend.ingredients.utils
and frontend.doe.validators patterns: page files stay thin glue.
"""
from __future__ import annotations

import pandas as pd

COMPOSITION_EDITOR_COLUMNS = ("ingredient", "role", "amount", "uom", "notes")
PARAMS_EDITOR_COLUMNS = ("parameter", "source", "aggregation", "value")
PROCEDURE_EDITOR_COLUMNS = ("name", "ingredients", "equipment", "duration", "params")
CUSTOM_FIELD_COLUMNS = ("key", "value")

# Overview table widget key — its selection can go stale when a selected row
# is deleted; the delete dialog resets it (see dialogs.delete_dialog).
FORMULAS_TABLE_KEY = "formulas_table"

# Composition display columns (detail tab / version diff).
COMPOSITION_DISPLAY_COLUMNS = ("no", "ingredient", "role", "amount", "uom", "notes")


def _cell_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


# --- tags -----------------------------------------------------------------

def tags_to_text(tags: list[str] | None) -> str:
    return ", ".join(tags or [])


def tags_from_text(text: str) -> list[str]:
    return [part.strip() for part in (text or "").split(",") if part.strip()]


# --- custom fields (same pattern as Ingredients) ---------------------------

def custom_fields_to_df(custom_fields: dict[str, str] | None) -> pd.DataFrame:
    items = [(key, value) for key, value in (custom_fields or {}).items()]
    return pd.DataFrame(items, columns=CUSTOM_FIELD_COLUMNS)


def custom_fields_from_df(df: pd.DataFrame | None) -> dict[str, str]:
    result: dict[str, str] = {}
    if df is None or df.empty:
        return result
    for _, row in df.iterrows():
        key = _cell_text(row.get("key")).strip()
        value = _cell_text(row.get("value"))
        if key:
            result[key] = value
    return result


# --- ingredient options ----------------------------------------------------

def ingredient_options(records: list[dict]) -> tuple[list[str], dict[str, int]]:
    """Display options for the composition selectbox + display -> id map.

    Each option is "name · item_code" when an item code exists (matches
    the DOE drafting vocabulary), else just the name.
    """
    options: list[str] = []
    name_to_id: dict[str, int] = {}
    for record in records:
        label = record.get("name") or ""
        item_code = record.get("item_code")
        if item_code:
            label = f"{label} · {item_code}"
        if not label.strip():
            continue
        options.append(label)
        name_to_id[label] = int(record["id"])
    return options, name_to_id


# --- composition -----------------------------------------------------------

def composition_to_df(composition: list[dict] | None) -> pd.DataFrame:
    """Stored rows -> editor/display DataFrame (README §5.1 Q1)."""
    rows = [
        {
            "no": item.get("no"),
            "ingredient": item.get("ingredient_name"),
            "role": item.get("role"),
            "amount": item.get("amount"),
            "uom": item.get("uom"),
            "notes": item.get("notes"),
        }
        for item in composition or []
    ]
    return pd.DataFrame(rows, columns=COMPOSITION_DISPLAY_COLUMNS)


def composition_from_df(
    df: pd.DataFrame | None, name_to_id: dict[str, int]
) -> list[dict]:
    """Editor DataFrame -> stored rows.

    Rows without an ingredient and without an amount are treated as blank
    and dropped. ``no`` is assigned 1..n in row order.
    """
    result: list[dict] = []
    if df is None or df.empty:
        return result
    kept: list = []
    for _, row in df.iterrows():
        label = _cell_text(row.get("ingredient")).strip()
        amount = row.get("amount")
        amount_blank = amount is None or (
            isinstance(amount, float) and pd.isna(amount)
        )
        if not label and amount_blank:
            continue  # blank row
        kept.append(row)
    for i, row in enumerate(kept):
        label = _cell_text(row.get("ingredient")).strip()
        amount = row.get("amount")
        result.append(
            {
                "no": i + 1,
                "ingredient_id": name_to_id.get(label),
                "ingredient_name": label,
                "role": _cell_text(row.get("role")).strip() or None,
                "amount": amount
                if isinstance(amount, (int, float)) and not isinstance(amount, bool)
                else None,
                "uom": _cell_text(row.get("uom")).strip() or None,
                "notes": _cell_text(row.get("notes")).strip() or None,
            }
        )
    return result


# --- params ----------------------------------------------------------------

def params_to_df(params: list[dict] | None) -> pd.DataFrame:
    rows = [
        {
            "parameter": p.get("parameter"),
            "source": p.get("source"),
            "aggregation": p.get("aggregation") or "",
            "value": p.get("value"),
        }
        for p in params or []
    ]
    return pd.DataFrame(rows, columns=PARAMS_EDITOR_COLUMNS)


def params_from_df(df: pd.DataFrame | None) -> list[dict]:
    """Editor DataFrame -> stored rows; rows without a parameter are dropped."""
    result: list[dict] = []
    if df is None or df.empty:
        return result
    for _, row in df.iterrows():
        parameter = _cell_text(row.get("parameter")).strip()
        if not parameter:
            continue
        result.append(
            {
                "parameter": parameter,
                "source": _cell_text(row.get("source")).strip() or None,
                "aggregation": _cell_text(row.get("aggregation")).strip() or None,
                "value": _cell_text(row.get("value")).strip() or None,
            }
        )
    return result


# --- procedure -------------------------------------------------------------

def _params_to_text(params: dict[str, str] | None) -> str:
    return "; ".join(f"{key}={value}" for key, value in (params or {}).items())


def _params_from_text(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in (text or "").split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, value = part.split("=", 1)
            result[key.strip()] = value.strip()
        else:
            result[part] = ""
    return result


def _ingredients_to_text(ingredients: list[dict] | None) -> str:
    names = [
        item.get("ingredient_name", "")
        for item in ingredients or []
        if item.get("ingredient_name")
    ]
    return ", ".join(names)


def procedure_to_df(procedure: list[dict] | None) -> pd.DataFrame:
    rows = [
        {
            "name": step.get("name"),
            "ingredients": _ingredients_to_text(step.get("ingredients")),
            "equipment": step.get("equipment"),
            "duration": step.get("duration"),
            "params": _params_to_text(step.get("params")),
        }
        for step in procedure or []
    ]
    return pd.DataFrame(rows, columns=PROCEDURE_EDITOR_COLUMNS)


def procedure_from_df(
    df: pd.DataFrame | None, name_to_id: dict[str, int]
) -> list[dict]:
    """Editor DataFrame -> stored steps.

    Ingredients are comma-separated display names, resolved to
    {ingredient_id, ingredient_name} pairs; processing params are
    "key=value; key=value" text.
    """
    result: list[dict] = []
    if df is None or df.empty:
        return result
    for _, row in df.iterrows():
        name = _cell_text(row.get("name")).strip()
        if not name:
            continue
        ingredients: list[dict] = []
        for label in _cell_text(row.get("ingredients")).split(","):
            label = label.strip()
            if not label:
                continue
            ingredients.append(
                {"ingredient_id": name_to_id.get(label), "ingredient_name": label}
            )
        result.append(
            {
                "name": name,
                "ingredients": ingredients,
                "equipment": _cell_text(row.get("equipment")).strip() or None,
                "duration": _cell_text(row.get("duration")).strip() or None,
                "params": _params_from_text(_cell_text(row.get("params"))),
            }
        )
    return result


# --- payload ---------------------------------------------------------------

def build_formula_payload(
    name: str,
    status: str,
    project: str = "",
    family: str = "",
    owner: str = "",
    tags: str = "",
    description: str = "",
    custom_fields: dict[str, str] | None = None,
    composition: list[dict] | None = None,
    params: list[dict] | None = None,
    procedure: list[dict] | None = None,
) -> dict:
    """Build a service payload from form values (blank strings -> None)."""
    return {
        "name": name.strip(),
        "status": status,
        "project": project.strip() or None,
        "family": family.strip() or None,
        "owner": owner.strip() or None,
        "tags": tags_from_text(tags),
        "description": description.strip() or None,
        "custom_fields": custom_fields or {},
        "composition": composition or [],
        "params": params or [],
        "procedure": procedure or [],
    }


# --- derived values --------------------------------------------------------

def derive_percentages(composition: list[dict] | None) -> list[float] | None:
    """Mass % of each row vs the total (README Q10).

    Returns None when not computable — no rows, missing/empty UOM, mixed
    UOMs, non-numeric amounts, or non-positive total. The UI shows "—".
    """
    rows = composition or []
    if not rows:
        return None
    uoms = {row.get("uom") for row in rows}
    if not uoms or None in uoms or "" in uoms or len(uoms) != 1:
        return None
    amounts = [row.get("amount") for row in rows]
    if any(
        not isinstance(a, (int, float)) or isinstance(a, bool) for a in amounts
    ):
        return None
    total = sum(amounts)
    if total <= 0:
        return None
    return [a / total * 100 for a in amounts]


def formula_stats(record: dict) -> dict[str, int]:
    """Attribute stats for the overview table (README §1).

    Batches/samples are placeholders (0) until the Lab module lands
    (README §6).
    """
    return {
        "ingredients": len(record.get("composition") or []),
        "steps": len(record.get("procedure") or []),
        "batches": 0,
        "samples": 0,
    }


# --- versions diff ---------------------------------------------------------

def _row_key(row: dict) -> tuple:
    return (
        row.get("ingredient_id"),
        row.get("ingredient_name"),
        row.get("role"),
        row.get("amount"),
        row.get("uom"),
        row.get("notes"),
    )


def diff_compositions(old: list[dict] | None, new: list[dict] | None) -> dict:
    """Compare two composition versions by row number (README Q2).

    Returns {"old": display rows, "new": display rows, "changed": [no, ...]}
    where "changed" lists the row numbers that differ (added, removed or
    edited). Display rows use COMPOSITION_DISPLAY_COLUMNS so the UI can
    render both sides side-by-side.
    """
    old_by_no = {row.get("no"): row for row in (old or []) if row.get("no") is not None}
    new_by_no = {row.get("no"): row for row in (new or []) if row.get("no") is not None}

    changed: list[int] = []
    for no in sorted(set(old_by_no) | set(new_by_no)):
        old_row = old_by_no.get(no)
        new_row = new_by_no.get(no)
        if old_row is None or new_row is None or _row_key(old_row) != _row_key(new_row):
            changed.append(no)

    def _display(rows: dict) -> list[dict]:
        return [
            {
                "no": no,
                "ingredient": r.get("ingredient_name"),
                "role": r.get("role"),
                "amount": r.get("amount"),
                "uom": r.get("uom"),
                "notes": r.get("notes"),
            }
            for no, r in sorted(rows.items())
        ]

    return {"old": _display(old_by_no), "new": _display(new_by_no), "changed": changed}
