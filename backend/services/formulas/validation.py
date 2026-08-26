"""Pure validation for formula records.

No I/O, no streamlit — returns a list of human-readable problem strings
(empty list means valid). Mirrors the backend.services.ingredients
validation pattern; shared by the service tests and the gateway
(docs/TEST_STRATEGIES.md §4.2).
"""
from __future__ import annotations

from typing import Any

from backend.services.formulas.schema import FORMULA_STATUSES, PARAM_AGGREGATIONS


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _string_field_ok(value: Any) -> bool:
    return value is None or isinstance(value, str)


def validate_formula(data: dict[str, Any]) -> list[str]:
    """Validate a formula record (create or update payload).

    Service-managed fields (id, version, created_at, updated_at) are
    ignored here — the store owns them.
    """
    problems: list[str] = []

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append("name is required and must be a non-empty string.")

    status = data.get("status")
    if status not in FORMULA_STATUSES:
        allowed = ", ".join(FORMULA_STATUSES)
        problems.append(f"status must be one of: {allowed}.")

    for field in ("project", "family", "owner", "description"):
        if not _string_field_ok(data.get(field)):
            problems.append(f"{field} must be a string.")

    tags = data.get("tags")
    if tags is not None:
        if not isinstance(tags, list) or not all(
            isinstance(tag, str) for tag in tags
        ):
            problems.append("tags must be a list of strings.")

    custom_fields = data.get("custom_fields")
    if custom_fields is not None:
        if not isinstance(custom_fields, dict):
            problems.append("custom_fields must be a mapping of name -> value.")
        else:
            for key, value in custom_fields.items():
                if not isinstance(key, str) or not key.strip():
                    problems.append(
                        "custom_fields keys must be non-empty strings."
                    )
                    break
                if not isinstance(value, str):
                    problems.append(
                        f"custom_fields value for '{key}' must be a string."
                    )
                    break

    problems += _validate_composition(data.get("composition"))
    problems += _validate_params(data.get("params"))
    problems += _validate_procedure(data.get("procedure"))

    return problems


def _validate_composition(composition: Any) -> list[str]:
    if composition is None:
        return []
    problems: list[str] = []
    if not isinstance(composition, list):
        return ["composition must be a list of rows."]
    for i, row in enumerate(composition):
        label = f"composition row {i + 1}"
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
        for field in ("role", "uom", "notes"):
            if not _string_field_ok(row.get(field)):
                problems.append(f"{label}: {field} must be a string.")
    return problems


def _validate_params(params: Any) -> list[str]:
    if params is None:
        return []
    problems: list[str] = []
    if not isinstance(params, list):
        return ["params must be a list of rows."]
    for i, row in enumerate(params):
        label = f"params row {i + 1}"
        if not isinstance(row, dict):
            problems.append(f"{label} must be an object.")
            continue
        if not isinstance(row.get("parameter"), str) or not row.get(
            "parameter"
        ).strip():
            problems.append(f"{label}: parameter is required.")
        for field in ("source", "value"):
            if not _string_field_ok(row.get(field)):
                problems.append(f"{label}: {field} must be a string.")
        aggregation = row.get("aggregation")
        if aggregation not in (None, "") and aggregation not in PARAM_AGGREGATIONS:
            allowed = ", ".join(PARAM_AGGREGATIONS)
            problems.append(f"{label}: aggregation must be one of: {allowed}.")
    return problems


def _validate_procedure(procedure: Any) -> list[str]:
    if procedure is None:
        return []
    problems: list[str] = []
    if not isinstance(procedure, list):
        return ["procedure must be a list of steps."]
    for i, step in enumerate(procedure):
        label = f"procedure step {i + 1}"
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
            if not isinstance(params, dict):
                problems.append(f"{label}: params must be a mapping of key -> value.")
            else:
                for key, value in params.items():
                    if not isinstance(key, str) or not key.strip():
                        problems.append(
                            f"{label}: params keys must be non-empty strings."
                        )
                        break
                    if not isinstance(value, str):
                        problems.append(
                            f"{label}: params value for '{key}' must be a string."
                        )
                        break
    return problems
