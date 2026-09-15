"""Pure validation for sample and transfer records.

No I/O, no streamlit — returns a list of human-readable problem strings
(empty list means valid). Mirrors the backend.services.batches /
ingredients validation pattern; shared by the service tests and the
gateway (docs/TEST_STRATEGIES.md §4.2).

Service-managed fields (id, created_at, updated_at) are ignored here — the
store/gateway own them. Policy that is not payload shape — code uniqueness,
the one-retention invariant, the read-only retention row and the delete
guard — lives in the gateway (README Q7/Q8/Q11/Q12), not here.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from backend.services.samples.schema import (
    SAMPLE_CODE_ALPHABET,
    SAMPLE_CODE_LENGTH,
    SAMPLE_ORIGINS,
    SAMPLE_STATUSES,
    STORAGE_CONDITIONS,
    TRANSFER_KINDS,
)


def _string_field_ok(value: Any) -> bool:
    return value is None or isinstance(value, str)


def is_valid_sample_code(code: Any) -> bool:
    """Exactly ``SAMPLE_CODE_LENGTH`` characters from the alphabet.

    The alphabet is uppercase, so a lowercase code is invalid — callers
    normalize with ``strip().upper()`` before validating (README Q11).
    """
    if not isinstance(code, str):
        return False
    if len(code) != SAMPLE_CODE_LENGTH:
        return False
    return all(char in SAMPLE_CODE_ALPHABET for char in code)


def is_iso_date(value: Any) -> bool:
    """A non-empty ISO date string (YYYY-MM-DD)."""
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        date.fromisoformat(value.strip())
    except ValueError:
        return False
    return True


def validate_sample(data: dict[str, Any]) -> list[str]:
    """Validate a sample record (create or update payload).

    ``retention`` (the initial-transfer payload) is not part of the sample
    record; the gateway validates it separately.
    """
    problems: list[str] = []

    code = data.get("sample_code")
    if not is_valid_sample_code(code):
        problems.append(
            f"sample_code must be exactly {SAMPLE_CODE_LENGTH} characters "
            f"from '{SAMPLE_CODE_ALPHABET}'."
        )

    origin = data.get("origin")
    if origin not in SAMPLE_ORIGINS:
        allowed = ", ".join(SAMPLE_ORIGINS)
        problems.append(f"origin must be one of: {allowed}.")

    batch_id = data.get("batch_id")
    if origin == "batch":
        if not isinstance(batch_id, int) or isinstance(batch_id, bool):
            problems.append(
                "batch_id is required and must be an integer when origin "
                "is 'batch'."
            )
    elif origin == "benchmark":
        if batch_id is not None:
            problems.append(
                "batch_id must be null when origin is 'benchmark'."
            )

    if not _string_field_ok(data.get("source")):
        problems.append("source must be a string.")

    if not is_iso_date(data.get("taken_at")):
        problems.append(
            "taken_at is required and must be an ISO date string "
            "(YYYY-MM-DD)."
        )

    status = data.get("status")
    if status not in SAMPLE_STATUSES:
        allowed = ", ".join(SAMPLE_STATUSES)
        problems.append(f"status must be one of: {allowed}.")

    if not _string_field_ok(data.get("notes")):
        problems.append("notes must be a string.")

    return problems


def validate_transfer(data: dict[str, Any]) -> list[str]:
    """Validate a sample transfer (retention or dispatch) payload."""
    problems: list[str] = []

    kind = data.get("kind")
    if kind not in TRANSFER_KINDS:
        allowed = ", ".join(TRANSFER_KINDS)
        problems.append(f"kind must be one of: {allowed}.")

    to_team = data.get("to_team")
    if kind == "dispatch":
        if not isinstance(to_team, str) or not to_team.strip():
            problems.append(
                "to_team is required and must be a non-empty string for a "
                "dispatch transfer."
            )
    elif kind == "retention":
        if to_team not in (None, ""):
            problems.append(
                "to_team must be empty for a retention transfer."
            )

    if not is_iso_date(data.get("sent_at")):
        problems.append(
            "sent_at is required and must be an ISO date string "
            "(YYYY-MM-DD)."
        )

    condition = data.get("storage_condition")
    if condition not in STORAGE_CONDITIONS:
        allowed = ", ".join(STORAGE_CONDITIONS)
        problems.append(
            f"storage_condition must be one of: {allowed}."
        )

    for field in ("sent_by", "notes"):
        if not _string_field_ok(data.get(field)):
            problems.append(f"{field} must be a string.")

    return problems
