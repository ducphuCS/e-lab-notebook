"""Pure validation for batch records.

No I/O, no streamlit — returns a list of human-readable problem strings
(empty list means valid). Mirrors the backend.services.ingredients /
backend.services.formulas validation pattern; shared by the service tests
and the gateway (docs/TEST_STRATEGIES.md §4.2).

Service-managed fields (id, batch_code, created_at, updated_at) are
ignored here — the store/gateway own them. Policy guards that are not
payload shape — delete only while 'planned', plan frozen once the batch
has left 'planned' — live in the gateway (README Q1/Q6), not here.
"""
from __future__ import annotations

from typing import Any

from backend.services.batches.schema import BATCH_STATUSES


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _string_field_ok(value: Any) -> bool:
    return value is None or isinstance(value, str)


def validate_batch(data: dict[str, Any]) -> list[str]:
    """Validate a batch record (create or update payload)."""
    problems: list[str] = []

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append("name is required and must be a non-empty string.")

    status = data.get("status")
    if status not in BATCH_STATUSES:
        allowed = ", ".join(BATCH_STATUSES)
        problems.append(f"status must be one of: {allowed}.")

    formula_id = data.get("formula_id")
    if not isinstance(formula_id, int):
        problems.append("formula_id is required and must be an integer.")

    formula_name = data.get("formula_name")
    if not isinstance(formula_name, str) or not formula_name.strip():
        problems.append(
            "formula_name is required and must be a non-empty string."
        )

    formula_version = data.get("formula_version")
    if not isinstance(formula_version, int) or formula_version < 1:
        problems.append(
            "formula_version is required and must be an integer >= 1."
        )

    owner = data.get("owner")
    if not _string_field_ok(owner):
        problems.append("owner must be a string.")

    problems += _validate_planned(data.get("planned"))
    problems += _validate_actual(data.get("actual"))

    return problems


# --- planned -----------------------------------------------------------

def _validate_planned(planned: Any) -> list[str]:
    """The plan is the frozen snapshot of what the batch will make:
    target yield + composition scaled to it + the formula's procedure
    snapshot (README Q1/Q3/Q8).
    """
    problems: list[str] = []
    if not isinstance(planned, dict):
        return ["planned must be an object (target yield + composition)."]

    target_yield = planned.get("target_yield")
    if target_yield is not None:
        if not isinstance(target_yield, dict):
            problems.append("planned.target_yield must be an object.")
        else:
            amount = target_yield.get("amount")
            if not _is_number(amount) or amount < 0:
                problems.append(
                    "planned.target_yield.amount must be a non-negative number."
                )
            if not _string_field_ok(target_yield.get("uom")):
                problems.append("planned.target_yield.uom must be a string.")

    composition = planned.get("composition")
    if not isinstance(composition, list) or not composition:
        problems.append(
            "planned.composition must be a non-empty list of ingredient rows."
        )
    else:
        for i, row in enumerate(composition):
            label = f"planned.composition row {i + 1}"
            if not isinstance(row, dict):
                problems.append(f"{label} must be an object.")
                continue
            if not isinstance(row.get("no"), int):
                problems.append(f"{label}: no must be an integer.")
            if not isinstance(row.get("ingredient_id"), int):
                problems.append(f"{label}: ingredient_id must be an integer.")
            if not isinstance(row.get("ingredient_name"), str) or not row.get(
                "ingredient_name"
            ).strip():
                problems.append(f"{label}: ingredient_name is required.")
            amount = row.get("amount")
            if not _is_number(amount) or amount < 0:
                problems.append(
                    f"{label}: amount must be a non-negative number."
                )
            for field in ("uom", "notes"):
                if not _string_field_ok(row.get(field)):
                    problems.append(f"{label}: {field} must be a string.")

    processing = planned.get("processing")
    if processing is not None:
        if not isinstance(processing, list):
            problems.append(
                "planned.processing must be a list of procedure steps."
            )
        else:
            problems += _validate_processing_steps(processing, "planned.processing")

    return problems


def _validate_processing_steps(steps: list[Any], where: str) -> list[str]:
    """Snapshot of the formula's procedure (README Q1, Q8): the Processing
    tab shows it read-only in v0; the future step-by-step execution log
    builds on it. Validated lightly — it is a copy of an already-validated
    formula procedure.
    """
    problems: list[str] = []
    for i, step in enumerate(steps):
        label = f"{where} step {i + 1}"
        if not isinstance(step, dict):
            problems.append(f"{label} must be an object.")
            continue
        if not isinstance(step.get("name"), str) or not step.get("name").strip():
            problems.append(f"{label}: name is required.")
        for field in ("equipment", "duration"):
            if not _string_field_ok(step.get(field)):
                problems.append(f"{label}: {field} must be a string.")

        ingredients = step.get("ingredients")
        if ingredients is not None:
            if not isinstance(ingredients, list):
                problems.append(f"{label}: ingredients must be a list.")
            else:
                for item in ingredients:
                    if not isinstance(item, dict):
                        problems.append(
                            f"{label}: ingredients items must be objects."
                        )
                        break
                    if not isinstance(item.get("ingredient_id"), int):
                        problems.append(
                            f"{label}: ingredients item ingredient_id must be an integer."
                        )
                        break
                    if not isinstance(item.get("ingredient_name"), str) or not item.get(
                        "ingredient_name"
                    ).strip():
                        problems.append(
                            f"{label}: ingredients item ingredient_name is required."
                        )
                        break

        params = step.get("params")
        if params is not None:
            if not isinstance(params, list):
                problems.append(
                    f"{label}: params must be a list of attributes "
                    "(name, value, unit)."
                )
            else:
                for j, item in enumerate(params):
                    p_label = f"{label} params item {j + 1}"
                    if not isinstance(item, dict):
                        problems.append(f"{p_label} must be an object.")
                        continue
                    if not isinstance(item.get("name"), str) or not item.get(
                        "name"
                    ).strip():
                        problems.append(f"{p_label}: name is required.")
                    for field in ("value", "unit"):
                        if not _string_field_ok(item.get(field)):
                            problems.append(
                                f"{p_label}: {field} must be a string."
                            )
    return problems


# --- actual ------------------------------------------------------------

def _validate_actual(actual: Any) -> list[str]:
    """Recorded reality (README Q2): per-ingredient actual amounts (one per
    planned row), actual yield, observations. No processing actuals in v0
    (Q8). Rows may be partially recorded, so the checks are type-only.
    """
    problems: list[str] = []
    if actual is None:
        return problems
    if not isinstance(actual, dict):
        return ["actual must be an object."]

    composition = actual.get("composition")
    if composition is not None:
        if not isinstance(composition, list):
            problems.append("actual.composition must be a list of rows.")
        else:
            for i, row in enumerate(composition):
                label = f"actual.composition row {i + 1}"
                if not isinstance(row, dict):
                    problems.append(f"{label} must be an object.")
                    continue
                if "no" in row and not isinstance(row.get("no"), int):
                    problems.append(f"{label}: no must be an integer.")
                if "ingredient_id" in row and not isinstance(
                    row.get("ingredient_id"), int
                ):
                    problems.append(f"{label}: ingredient_id must be an integer.")
                if "ingredient_name" in row and not isinstance(
                    row.get("ingredient_name"), str
                ):
                    problems.append(f"{label}: ingredient_name must be a string.")
                if "amount" in row:
                    amount = row.get("amount")
                    if not _is_number(amount) or amount < 0:
                        problems.append(
                            f"{label}: amount must be a non-negative number."
                        )
                for field in ("uom", "note"):
                    if field in row and not _string_field_ok(row.get(field)):
                        problems.append(f"{label}: {field} must be a string.")

    yield_ = actual.get("yield")
    if yield_ is not None:
        if not isinstance(yield_, dict):
            problems.append("actual.yield must be an object.")
        else:
            if "amount" in yield_:
                amount = yield_.get("amount")
                if not _is_number(amount) or amount < 0:
                    problems.append(
                        "actual.yield.amount must be a non-negative number."
                    )
            if "uom" in yield_ and not _string_field_ok(yield_.get("uom")):
                problems.append("actual.yield.uom must be a string.")

    observations = actual.get("observations")
    if observations is not None and not isinstance(observations, str):
        problems.append("actual.observations must be a string.")

    return problems
