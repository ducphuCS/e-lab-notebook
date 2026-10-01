"""Pure validation for test-report and test-result records.

No I/O, no streamlit — returns a list of human-readable problem strings
(empty list means valid). Mirrors the backend.services.samples /
batches validation pattern; shared by the service tests and the gateway
(docs/TEST_STRATEGIES.md §4.2).

Service-managed fields (id, created_at, updated_at) are ignored here — the
store/gateway own them. Whether a referenced sample/transfer exists is a
cross-service concern owned by the page (samples live in another DB), not
this pure layer.
"""
from __future__ import annotations

from datetime import date
from typing import Any


def _string_field_ok(value: Any) -> bool:
    return value is None or isinstance(value, str)


def is_iso_date(value: Any) -> bool:
    """A non-empty ISO date string (YYYY-MM-DD)."""
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        date.fromisoformat(value.strip())
    except ValueError:
        return False
    return True


def is_number(value: Any) -> bool:
    """A real number — ``bool`` is rejected (it is an ``int`` subclass)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_report(data: dict[str, Any]) -> list[str]:
    """Validate a test-report header (create or update payload)."""
    problems: list[str] = []

    test_method = data.get("test_method")
    if not isinstance(test_method, str) or not test_method.strip():
        problems.append(
            "test_method is required and must be a non-empty string."
        )

    if not is_iso_date(data.get("evaluation_date")):
        problems.append(
            "evaluation_date is required and must be an ISO date string "
            "(YYYY-MM-DD)."
        )

    for field in (
        "person_in_charge",
        "methodology",
        "equipment",
        "panel",
        "notes",
    ):
        if not _string_field_ok(data.get(field)):
            problems.append(f"{field} must be a string.")

    return problems


def validate_result(data: dict[str, Any]) -> list[str]:
    """Validate one result row (one evaluated sample within a report)."""
    problems: list[str] = []

    for field in ("report_id", "sample_id", "transfer_id"):
        value = data.get(field)
        if not isinstance(value, int) or isinstance(value, bool):
            problems.append(
                f"{field} is required and must be an integer."
            )

    parameter = data.get("parameter")
    if not isinstance(parameter, str) or not parameter.strip():
        problems.append(
            "parameter is required and must be a non-empty string."
        )

    if not is_number(data.get("value")):
        problems.append("value is required and must be a number.")

    for field in ("unit", "notes"):
        if not _string_field_ok(data.get(field)):
            problems.append(f"{field} must be a string.")

    return problems
