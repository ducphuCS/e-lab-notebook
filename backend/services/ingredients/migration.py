"""Temporary migration helpers for the ingredient custom-field shape.

Legacy (v0, before 2026-09-07):  {"name": "value"}
Current (since commit 9e1c865):  {"name": {"value": ..., "unit": ...}}

Validation (validation.py) accepts only the current shape, so a row still
stored in the legacy shape fails every read. These pure helpers detect and
rewrite exactly those rows; the Ingredients page exposes a temporary button
until every real database has been migrated.

TEMP — remove this module, the store/gateway entry points and the page
button once every user has migrated (frontend/ingredients/README.md §11).
"""
from __future__ import annotations

from typing import Any


def has_legacy_entries(custom_fields: dict[str, Any]) -> bool:
    """True if any entry still uses the legacy plain-value shape.

    Current-shape entries are dicts ({value, unit}); anything else (v0
    stored plain strings) is legacy and needs rewriting.
    """
    return any(not isinstance(entry, dict) for entry in custom_fields.values())


def to_new_shape(custom_fields: dict[str, Any]) -> dict[str, Any]:
    """Rewrite legacy entries to the current {value, unit} shape.

    Non-dict entries (v0 stored plain strings) become
    {"value": <text>, "unit": ""}; entries already in the current shape
    pass through untouched. Idempotent.
    """
    result: dict[str, Any] = {}
    for key, entry in custom_fields.items():
        if isinstance(entry, dict):
            result[key] = entry
        else:
            result[key] = {
                "value": "" if entry is None else str(entry),
                "unit": "",
            }
    return result
