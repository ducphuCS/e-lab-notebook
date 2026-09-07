"""Gateway client for the Ingredients service.

The ONLY code allowed to talk to backend services over HTTP
(docs/TEST_STRATEGIES.md §3). For the v0 prototype (README Q6) the
transport is in-process: the gateway calls the SQLite-backed store
directly. When a real service exists, only this module changes (HTTP +
JSON); pages keep calling the same functions.

Gateway duties, applied here:
  1. route to the right service  -> the ingredients store (in-process)
  2. validate requests before they leave -> ``validate_ingredient``
  3. validate responses on the way back -> ``validate_record``
  4. uniform error shape -> ``GatewayError``
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.services.ingredients import store
from backend.services.ingredients.schema import INGREDIENT_FIELDS
from backend.services.ingredients.validation import (
    validate_custom_fields,
    validate_ingredient,
)


class GatewayError(Exception):
    """Uniform error shape for every service failure (gateway duty #4).

    ``problems`` carries human-readable validation messages the UI can show.
    """

    def __init__(self, message: str, problems: list[str] | None = None) -> None:
        self.problems = problems or []
        super().__init__(message)


def connect(path: str | Path | None = None) -> Any:
    """Open the service connection (in-memory if ``path`` is None).

    The page calls this once and passes the connection to every gateway
    function; the gateway itself holds no global state.
    """
    return store.connect(path)


def validate_record(data: dict[str, Any]) -> list[str]:
    """Contract enforcement: check a service response record's shape.

    Pure and public so contract tests can feed golden JSON fixtures
    directly (tests/contracts/): *given this service response, the
    gateway accepts it; given malformed, it rejects it*.
    """
    problems: list[str] = []
    missing = [field for field in INGREDIENT_FIELDS if field not in data]
    if missing:
        problems.append(
            f"response record missing fields: {', '.join(missing)}."
        )
    if not isinstance(data.get("id"), int):
        problems.append("response record 'id' must be an integer.")
    custom_fields = data.get("custom_fields")
    if custom_fields is not None:
        if not isinstance(custom_fields, dict):
            problems.append("response record 'custom_fields' must be an object.")
        else:
            # Same shape as request payloads: {name: {value, unit}}. A
            # legacy plain-string mapping fails here, so the read path
            # never surfaces legacy data to the page.
            problems.extend(validate_custom_fields(custom_fields))
    return problems


def _raise_if_problems(problems: list[str], message: str) -> None:
    if problems:
        raise GatewayError(message, problems)


def _checked(record: dict[str, Any], message: str) -> dict[str, Any]:
    _raise_if_problems(validate_record(record), message)
    return record


def list_ingredients(conn: Any) -> list[dict[str, Any]]:
    records = store.list_ingredients(conn)
    for record in records:
        _raise_if_problems(
            validate_record(record),
            "service returned a malformed ingredient record.",
        )
    return records


def get_ingredient(conn: Any, ingredient_id: int) -> dict[str, Any] | None:
    record = store.get_ingredient(conn, ingredient_id)
    if record is None:
        return None
    return _checked(record, "service returned a malformed ingredient record.")


def create_ingredient(conn: Any, data: dict[str, Any]) -> dict[str, Any]:
    problems = validate_ingredient(data)
    if problems:
        raise GatewayError("Cannot create ingredient.", problems)
    new_id = store.create_ingredient(conn, data)
    record = store.get_ingredient(conn, new_id)
    return _checked(record, "service returned a malformed ingredient record.")


def update_ingredient(
    conn: Any, ingredient_id: int, data: dict[str, Any]
) -> dict[str, Any]:
    current = store.get_ingredient(conn, ingredient_id)
    if current is None:
        raise GatewayError(f"Ingredient {ingredient_id} not found.")
    merged = {**current, **data}
    problems = validate_ingredient(merged)
    if problems:
        raise GatewayError("Cannot update ingredient.", problems)
    store.update_ingredient(conn, ingredient_id, merged)
    record = store.get_ingredient(conn, ingredient_id)
    return _checked(record, "service returned a malformed ingredient record.")


def delete_ingredient(conn: Any, ingredient_id: int) -> bool:
    if not store.delete_ingredient(conn, ingredient_id):
        raise GatewayError(f"Ingredient {ingredient_id} not found.")
    return True


# ---------------------------------------------------------------------------
# TEMP — legacy custom-field migration (remove me).
# Entry points for the temporary in-app migration button
# (frontend/ingredients/README.md §11).
# ---------------------------------------------------------------------------


def count_legacy_custom_field_rows(conn: Any) -> int:
    """How many rows still store custom_fields in the legacy shape.

    TEMP — the page uses this to decide whether to show the migration
    button. Remove with the migration (see migration.py docstring).
    """
    return store.count_legacy_custom_field_rows(conn)


def migrate_legacy_custom_fields(conn: Any) -> int:
    """Rewrite legacy custom_fields rows in place; returns rows updated.

    Deliberately bypasses response validation: legacy rows fail the
    current-shape check by definition — rewriting them is the point.

    TEMP — remove with the migration (see migration.py docstring).
    """
    return store.migrate_legacy_custom_fields(conn)
