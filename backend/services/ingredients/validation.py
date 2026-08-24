"""Pure validation for ingredient records.

No I/O, no streamlit — returns a list of human-readable problem strings
(empty list means valid). Mirrors the frontend.doe.validators pattern
(docs/TEST_STRATEGIES.md §4.2), kept here so the service and gateway share
one validation source.
"""
from __future__ import annotations

from typing import Any

from backend.services.ingredients.schema import INGREDIENT_STATES


def validate_ingredient(data: dict[str, Any]) -> list[str]:
    """Validate an ingredient record (create or update payload)."""
    problems: list[str] = []

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append("name is required and must be a non-empty string.")

    for field in ("item_code", "item_description", "supplier", "notes", "uom"):
        value = data.get(field)
        if value is not None and not isinstance(value, str):
            problems.append(f"{field} must be a string.")

    state = data.get("state")
    if state is not None and state not in INGREDIENT_STATES:
        allowed = ", ".join(INGREDIENT_STATES)
        problems.append(f"state must be one of: {allowed}.")

    custom_fields = data.get("custom_fields")
    if custom_fields is not None:
        if not isinstance(custom_fields, dict):
            problems.append("custom_fields must be a mapping of name -> value.")
        else:
            for key, value in custom_fields.items():
                if not isinstance(key, str) or not key.strip():
                    problems.append("custom_fields keys must be non-empty strings.")
                    break
                if not isinstance(value, str):
                    problems.append(f"custom_fields value for '{key}' must be a string.")
                    break

    return problems
