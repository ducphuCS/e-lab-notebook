"""Pure helpers for the Batches pages (no streamlit).

Extracted so they are unit-testable without a UI runtime
(docs/TEST_STRATEGIES.md §4.2). Mirrors the frontend.formulas.utils /
frontend.ingredients.utils patterns: page files stay thin glue.

Covers the v0 batch logic (frontend/batches/README.md): the planned
snapshot (formula composition scaled to a target yield, §Q3), the
planned-vs-actual composition editor with the same-unit deviation guard
(§5.1), and the read-only processing snapshot (Q8).
"""
from __future__ import annotations

import pandas as pd

# Overview table widget key — its selection can go stale when a selected
# row is deleted; the delete dialog resets it (mirrors Formulas).
BATCHES_TABLE_KEY = "batches_table"

# Plan editor columns (edit-while-planned): fixed rows from the plan.
PLAN_EDIT_COLUMNS = ("no", "ingredient", "amount", "uom", "notes")

# Composition tab editor columns — the visible set, in display order.
# `deviation` is derived in the UI and never stored (same-unit rule).
# Identity is carried by two extra columns (COMPOSITION_EDITOR_HIDDEN_COLUMNS)
# appended to the editor DataFrame; the page hides them via the editor's
# column_order (st.data_editor keeps omitted columns in the data, read-only)
# so actual rows can be rebuilt from the editor without touching the
# Ingredients service.
COMPOSITION_EDITOR_COLUMNS = (
    "no",
    "ingredient",
    "planned",
    "plan_uom",
    "actual",
    "actual_uom",
    "deviation",
    "note",
)

# Hidden identity columns riding along after the visible ones (see above).
# Kept separate from COMPOSITION_EDITOR_COLUMNS so pages can pass the
# visible tuple as the editor's column_order.
COMPOSITION_EDITOR_HIDDEN_COLUMNS = ("ingredient_id", "ingredient_name")


def _num(value: object) -> float | None:
    """Numeric cell -> float, tolerating None/NaN/non-numeric input."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


# --- formula picker --------------------------------------------------------

def formula_options(records: list[dict]) -> tuple[list[str], dict[str, int]]:
    """Display labels + label -> formula id for the create dialog.

    Names are unique in practice; when two formulas share a name the id is
    appended so the selectbox options stay unambiguous.
    """
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in records:
        name = (record.get("name") or "").strip()
        if name in seen:
            duplicates.add(name)
        seen.add(name)

    options: list[str] = []
    label_to_id: dict[str, int] = {}
    for record in records:
        name = (record.get("name") or "").strip()
        if not name:
            continue
        label = name if name not in duplicates else f"{name} (id {record['id']})"
        options.append(label)
        label_to_id[label] = int(record["id"])
    return options, label_to_id


# --- planned snapshot (README Q1/Q3) --------------------------------------

def normalize_plan_rows(composition: list[dict] | None) -> list[dict]:
    """Formula composition rows -> batch plan row shape.

    Drops blank rows (no ingredient), renumbers ``no`` 1..n, and keeps only
    the fields the plan carries (no role — README §5.1).
    """
    rows: list[dict] = []
    for item in composition or []:
        name = (item.get("ingredient_name") or "").strip()
        if not name:
            continue
        rows.append(
            {
                "no": len(rows) + 1,
                "ingredient_id": item.get("ingredient_id"),
                "ingredient_name": name,
                "amount": item.get("amount"),
                "uom": item.get("uom"),
                "notes": item.get("notes"),
            }
        )
    return rows


def scale_guard_reason(rows: list[dict] | None) -> str | None:
    """Why the plan cannot be scaled to a target yield, or None if it can.

    Scaling needs every row to carry a numeric amount and all rows to share
    one non-empty uom (README §5.1 derived-value rule). Returns a
    human-readable reason when scaling is impossible.
    """
    rows = rows or []
    if not rows:
        return "the formula has no composition rows."
    uoms = {(row.get("uom") or "").strip() for row in rows}
    if not uoms or "" in uoms or len(uoms) != 1:
        return "composition rows use different units (or none)."
    amounts = [_num(row.get("amount")) for row in rows]
    if any(a is None for a in amounts):
        return "some composition rows have no amount."
    if sum(a for a in amounts if a is not None) <= 0:
        return "the composition amounts sum to zero."
    return None


def _scale_rows(rows: list[dict], target_amount: float) -> list[dict]:
    """Formula rows scaled by target ÷ Σ amounts (rounded to 2 dp)."""
    total = sum(a for a in (_num(row.get("amount")) for row in rows) if a is not None)
    factor = target_amount / total if total else 0.0
    scaled: list[dict] = []
    for row in rows:
        amount = _num(row.get("amount"))
        scaled.append(
            {
                **row,
                "amount": round(amount * factor, 2)
                if amount is not None
                else None,
            }
        )
    return scaled


def build_planned(
    formula: dict,
    target_amount: float | None = None,
    target_uom: str = "",
) -> dict | None:
    """The planned snapshot from a formula (README Q1/Q3).

    Returns None when the formula has no composition rows (nothing to plan
    from). Otherwise the plan always carries rows: scaled to the target
    when possible, copied from the formula as-is otherwise (README §5.1 —
    mixed units fall back to an unscaled plan). ``target_yield`` is stored
    only when a target amount was given and the scaling guard passes.
    """
    rows = normalize_plan_rows(formula.get("composition"))
    if not rows:
        return None

    planned: dict = {"composition": rows}
    if target_amount is not None and scale_guard_reason(rows) is None:
        planned["target_yield"] = {"amount": target_amount, "uom": target_uom}
        planned["composition"] = _scale_rows(rows, target_amount)
    # processing snapshot: the formula's procedure as-is (Q1/Q8) — the
    # read-only reference the future execution log builds on.
    planned["processing"] = list(formula.get("procedure") or [])
    return planned


# --- getters on a batch record --------------------------------------------

def target_yield(record: dict) -> dict | None:
    planned = record.get("planned") or {}
    return planned.get("target_yield")


def actual_yield(record: dict) -> dict | None:
    actual = record.get("actual") or {}
    return actual.get("yield")


def observations(record: dict) -> str:
    actual = record.get("actual") or {}
    return actual.get("observations") or ""


def planned_rows(record: dict) -> list[dict]:
    return (record.get("planned") or {}).get("composition") or []


def actual_rows(record: dict) -> list[dict]:
    return (record.get("actual") or {}).get("composition") or []


def yield_text(value: dict | None) -> str:
    """Pretty-print a {amount, uom} dict, e.g. "2500 g"."""
    if not value or _num(value.get("amount")) is None:
        return "—"
    amount = _num(value["amount"])
    uom = _text(value.get("uom"))
    text = f"{amount:g}"
    return f"{text} {uom}" if uom else text


def batch_stats(
    record: dict, sample_count: int = 0, report_count: int = 0
) -> dict[str, int]:
    """Overview stats. Both columns are real reverse links: sample count
    (Samples, 2026-09-15) and distinct test-report count (Test Reports,
    2026-10-01)."""
    return {
        "samples": sample_count or 0,
        "reports": report_count or 0,
    }


def samples_block_reason(sample_count: int | None) -> str | None:
    """Why a batch cannot be deleted, or None when deletion is allowed.

    A batch that produced samples cannot be deleted (README Q6 / the
    Samples letter's draft item 2) — samples carry the batch's identity.
    Mirrors Ingredients' ``formula_usage_block_reason``: the condition
    lives in another service, so the guard is enforced in the delete
    confirm and the store delete itself stays unconditional.
    """
    count = sample_count or 0
    if count <= 0:
        return None
    noun = "sample" if count == 1 else "samples"
    return f"{count} {noun} were taken from this batch."


# --- deviation (derived, never stored — README §5.1) ----------------------

def deviation(
    planned_amount: object,
    plan_uom: object,
    actual_amount: object,
    actual_uom: object,
) -> float | None:
    """actual − planned, only when both amounts are numeric and the units
    match; otherwise None (the UI shows "—"). Mirrors Formulas Q10."""
    planned = _num(planned_amount)
    actual = _num(actual_amount)
    if planned is None or actual is None:
        return None
    if not plan_uom or not actual_uom or _text(plan_uom) != _text(actual_uom):
        return None
    return round(actual - planned, 2)


# --- composition tab: planned vs actual editor ----------------------------

def composition_editor_df(record: dict) -> pd.DataFrame:
    """Merged planned-vs-actual editor rows (README §4 Composition tab).

    Visible columns: no, ingredient, planned, plan_uom, actual (editable),
    actual_uom (editable, prefilled from the plan), deviation (derived),
    note (editable). ingredient_id/ingredient_name are appended after them
    (hidden via the page's column_order) so actual rows keep their spec
    shape (README §5.1) when rebuilt from the editor.
    """
    planned = planned_rows(record)
    actual_by_no = {row.get("no"): row for row in actual_rows(record)}
    rows = []
    for row in planned:
        actual = actual_by_no.get(row.get("no"), {})
        planned_amount = _num(row.get("amount"))
        actual_amount = _num(actual.get("amount"))
        plan_uom = _text(row.get("uom"))
        actual_uom = _text(actual.get("uom")) or plan_uom
        rows.append(
            {
                "no": row.get("no"),
                "ingredient": row.get("ingredient_name"),
                "ingredient_id": row.get("ingredient_id"),
                "ingredient_name": row.get("ingredient_name"),
                "planned": planned_amount,
                "plan_uom": plan_uom,
                "actual": actual_amount,
                "actual_uom": actual_uom,
                "deviation": deviation(
                    planned_amount, plan_uom, actual_amount, actual_uom
                ),
                "note": actual.get("note"),
            }
        )
    return pd.DataFrame(
        rows,
        columns=COMPOSITION_EDITOR_COLUMNS + COMPOSITION_EDITOR_HIDDEN_COLUMNS,
    )


def actual_from_editor(df: pd.DataFrame | None) -> list[dict]:
    """Composition editor -> actual.composition rows (README §5.1).

    A row counts as recorded when it has an actual amount or a note;
    untouched rows (blank amount, blank note, uom just prefilled) are
    dropped. Actual rows keep the plan's no/ingredient ids so they can
    line up row by row on the next render.

    Identity keys (ingredient_id/ingredient_name) come from the editor's
    hidden columns and are emitted only when present and typed — never as
    None — so the rows pass backend validation (which type-checks keys it
    finds; README §5.1). Alignment on render is by ``no`` regardless.
    """
    result: list[dict] = []
    if df is None or df.empty:
        return result
    for _, row in df.iterrows():
        amount = _num(row.get("actual"))
        note = _text(row.get("note")).strip()
        if amount is None and not note:
            continue
        recorded: dict = {
            "no": row.get("no") if isinstance(row.get("no"), int) else None,
            "amount": amount,
            "uom": _text(row.get("actual_uom")).strip() or None,
            "note": note or None,
        }
        ingredient_id = row.get("ingredient_id")
        if isinstance(ingredient_id, int):
            recorded["ingredient_id"] = ingredient_id
        ingredient_name = row.get("ingredient_name")
        if isinstance(ingredient_name, str) and ingredient_name.strip():
            recorded["ingredient_name"] = ingredient_name
        result.append(recorded)
    return result


# --- plan editor (edit dialog, while 'planned') ---------------------------

def plan_editor_df(record: dict) -> pd.DataFrame:
    """Plan rows -> editor DataFrame for the edit dialog.

    Rows are fixed (they come from the formula); amount/uom/notes are
    editable so a planned batch can be fine-tuned (README decision
    2026-09-03 — plan editable only while 'planned').
    """
    rows = [
        {
            "no": row.get("no"),
            "ingredient": row.get("ingredient_name"),
            "amount": _num(row.get("amount")),
            "uom": row.get("uom"),
            "notes": row.get("notes"),
        }
        for row in planned_rows(record)
    ]
    return pd.DataFrame(rows, columns=PLAN_EDIT_COLUMNS)


def plan_from_editor_df(
    df: pd.DataFrame | None, planned: list[dict]
) -> list[dict]:
    """Plan editor -> planned.composition rows.

    Amounts/uoms/notes are read from the editor; identity comes from the
    original plan rows (matched by no), so the plan can never introduce an
    ingredient the formula does not contain.
    """
    original = {row.get("no"): row for row in planned}
    result: list[dict] = []
    if df is None or df.empty:
        return []
    for _, row in df.iterrows():
        no = row.get("no") if isinstance(row.get("no"), int) else None
        original_row = original.get(no)
        if original_row is None:
            continue
        result.append(
            {
                "no": no,
                "ingredient_id": original_row.get("ingredient_id"),
                "ingredient_name": original_row.get("ingredient_name"),
                "amount": _num(row.get("amount")),
                "uom": _text(row.get("uom")).strip() or None,
                "notes": _text(row.get("notes")).strip() or None,
            }
        )
    return result


# --- processing tab (read-only snapshot, Q8) ------------------------------

def processing_df(record: dict) -> pd.DataFrame:
    """Planned processing snapshot -> read-only rows.

    Flattens each procedure step's params (name/value/unit) one row per
    param; a step without params gets one row with blank param cells so
    every step is visible. v0 shows no actual processing values (README Q8).
    """
    steps = (record.get("planned") or {}).get("processing") or []
    rows = []
    for i, step in enumerate(steps):
        step_label = f"{i + 1}. {(step.get('name') or '').strip()}"
        params = step.get("params") or []
        if not params:
            rows.append(
                {
                    "step": step_label,
                    "equipment": step.get("equipment"),
                    "duration": step.get("duration"),
                    "parameter": None,
                    "value": None,
                    "unit": None,
                }
            )
            continue
        for param in params:
            rows.append(
                {
                    "step": step_label,
                    "equipment": step.get("equipment"),
                    "duration": step.get("duration"),
                    "parameter": param.get("name"),
                    "value": param.get("value"),
                    "unit": param.get("unit"),
                }
            )
    return pd.DataFrame(
        rows, columns=("step", "equipment", "duration", "parameter", "value", "unit")
    )
