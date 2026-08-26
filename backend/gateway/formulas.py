"""Gateway client for the Formulas service.

The ONLY code allowed to talk to backend services over HTTP
(docs/TEST_STRATEGIES.md §3). For the v0 prototype (README §5.2) the
transport is in-process: the gateway calls the SQLite-backed store
directly. When a real service exists, only this module changes (HTTP +
JSON); pages keep calling the same functions.

Gateway duties, applied here:
  1. route to the right service  -> the formulas store (in-process)
  2. validate requests before they leave -> ``validate_formula``
  3. validate responses on the way back -> ``validate_record``
  4. uniform error shape -> ``GatewayError``
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.services.formulas import store
from backend.services.formulas.schema import FORMULA_FIELDS
from backend.services.formulas.validation import validate_formula


class GatewayError(Exception):
    """Uniform error shape for every service failure (gateway duty #4).

    ``problems`` carries human-readable validation messages the UI can show.
    """

    def __init__(self, message: str, problems: list[str] | None = None) -> None:
        self.problems = problems or []
        super().__init__(message)


def connect(path: str | Path | None = None) -> Any:
    """Open the service connection (in-memory if ``path`` is None)."""
    return store.connect(path)


def validate_record(data: dict[str, Any]) -> list[str]:
    """Contract enforcement: check a service response record's shape.

    Pure and public so contract tests can feed golden JSON fixtures
    directly (tests/contracts/): *given this service response, the
    gateway accepts it; given malformed, it rejects it*.
    """
    problems: list[str] = []
    missing = [field for field in FORMULA_FIELDS if field not in data]
    if missing:
        problems.append(
            f"response record missing fields: {', '.join(missing)}."
        )
    if not isinstance(data.get("id"), int):
        problems.append("response record 'id' must be an integer.")
    if not isinstance(data.get("version"), int):
        problems.append("response record 'version' must be an integer.")
    for field in ("tags", "composition", "params", "procedure"):
        if data.get(field) is not None and not isinstance(data.get(field), list):
            problems.append(f"response record '{field}' must be an array.")
    custom_fields = data.get("custom_fields")
    if custom_fields is not None and not isinstance(custom_fields, dict):
        problems.append("response record 'custom_fields' must be an object.")
    return problems


def _validate_version_row(data: dict[str, Any]) -> list[str]:
    """Contract check for a version-history row (formula_versions)."""
    problems: list[str] = []
    for field in ("id", "formula_id", "version"):
        if not isinstance(data.get(field), int):
            problems.append(f"version row '{field}' must be an integer.")
    if not isinstance(data.get("snapshot"), dict):
        problems.append("version row 'snapshot' must be an object.")
    if not isinstance(data.get("created_at"), str):
        problems.append("version row 'created_at' must be a string.")
    return problems


def _raise_if_problems(problems: list[str], message: str) -> None:
    if problems:
        raise GatewayError(message, problems)


def _checked(record: dict[str, Any], message: str) -> dict[str, Any]:
    _raise_if_problems(validate_record(record), message)
    return record


def list_formulas(conn: Any) -> list[dict[str, Any]]:
    records = store.list_formulas(conn)
    for record in records:
        _raise_if_problems(
            validate_record(record),
            "service returned a malformed formula record.",
        )
    return records


def get_formula(conn: Any, formula_id: int) -> dict[str, Any] | None:
    record = store.get_formula(conn, formula_id)
    if record is None:
        return None
    return _checked(record, "service returned a malformed formula record.")


def create_formula(conn: Any, data: dict[str, Any]) -> dict[str, Any]:
    problems = validate_formula(data)
    if problems:
        raise GatewayError("Cannot create formula.", problems)
    new_id = store.create_formula(conn, data)
    record = store.get_formula(conn, new_id)
    return _checked(record, "service returned a malformed formula record.")


def update_formula(
    conn: Any, formula_id: int, data: dict[str, Any]
) -> dict[str, Any]:
    current = store.get_formula(conn, formula_id)
    if current is None:
        raise GatewayError(f"Formula {formula_id} not found.")
    merged = {**current, **data}
    problems = validate_formula(merged)
    if problems:
        raise GatewayError("Cannot update formula.", problems)
    store.update_formula(conn, formula_id, merged)
    record = store.get_formula(conn, formula_id)
    return _checked(record, "service returned a malformed formula record.")


def delete_formula(conn: Any, formula_id: int) -> bool:
    if not store.delete_formula(conn, formula_id):
        raise GatewayError(f"Formula {formula_id} not found.")
    return True


def duplicate_formula(
    conn: Any, source_id: int, new_name: str | None = None
) -> dict[str, Any]:
    current = store.get_formula(conn, source_id)
    if current is None:
        raise GatewayError(f"Formula {source_id} not found.")
    new_id = store.duplicate_formula(conn, source_id, new_name)
    record = store.get_formula(conn, new_id)
    return _checked(record, "service returned a malformed formula record.")


def list_formula_versions(conn: Any, formula_id: int) -> list[dict[str, Any]]:
    rows = store.list_formula_versions(conn, formula_id)
    for row in rows:
        _raise_if_problems(
            _validate_version_row(row),
            "service returned a malformed version row.",
        )
    return rows
