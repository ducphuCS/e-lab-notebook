"""Gateway client for the Samples service.

The ONLY code allowed to talk to backend services over HTTP
(docs/TEST_STRATEGIES.md §3). For the v0 prototype
(frontend/samples/README.md §5.3) the transport is in-process: the gateway
calls the SQLite-backed store directly. When a real service exists, only
this module changes (HTTP + JSON); pages keep calling the same functions.

Gateway duties, applied here:
  1. route to the right service      -> the samples store (in-process)
  2. validate requests before they leave -> ``validate_sample`` /
     ``validate_transfer``
  3. validate responses on the way back -> ``validate_record`` /
     ``validate_transfer_record``
  4. uniform error shape             -> ``GatewayError``

Policy guards from the letter live here too (README Q7/Q8/Q11/Q12):
  - identity/provenance fields (sample_code, origin, batch_id) are
    immutable after creation;
  - exactly one `retention` transfer per sample, created with it;
  - the retention row is read-only and non-deletable;
  - deletion is blocked by any `dispatch` (and, once Test Reports lands,
    by linked test reports) — the retention row never blocks.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.services.samples import store
from backend.services.samples.schema import (
    IMMUTABLE_FIELDS,
    SAMPLE_FIELDS,
    TRANSFER_FIELDS,
)
from backend.services.samples.validation import (
    validate_sample,
    validate_transfer,
)


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
    """Contract enforcement: check a service sample record's shape.

    Pure and public so contract tests can feed golden JSON fixtures
    directly (tests/contracts/).
    """
    problems: list[str] = []
    missing = [field for field in SAMPLE_FIELDS if field not in data]
    if missing:
        problems.append(
            f"response record missing fields: {', '.join(missing)}."
        )
    if not isinstance(data.get("id"), int):
        problems.append("response record 'id' must be an integer.")
    if not isinstance(data.get("sample_code"), str) or not data.get(
        "sample_code"
    ):
        problems.append(
            "response record 'sample_code' must be a non-empty string."
        )
    if not isinstance(data.get("origin"), str):
        problems.append("response record 'origin' must be a string.")
    batch_id = data.get("batch_id")
    if batch_id is not None and not isinstance(batch_id, int):
        problems.append("response record 'batch_id' must be an integer or null.")
    for field in ("source", "taken_at", "notes", "created_at", "updated_at"):
        if data.get(field) is not None and not isinstance(data.get(field), str):
            problems.append(f"response record '{field}' must be a string.")
    if not isinstance(data.get("status"), str):
        problems.append("response record 'status' must be a string.")
    return problems


def validate_transfer_record(data: dict[str, Any]) -> list[str]:
    """Contract check for a sample transfer response record."""
    problems: list[str] = []
    missing = [field for field in TRANSFER_FIELDS if field not in data]
    if missing:
        problems.append(
            f"transfer record missing fields: {', '.join(missing)}."
        )
    for field in ("id", "sample_id"):
        if not isinstance(data.get(field), int):
            problems.append(f"transfer record '{field}' must be an integer.")
    if not isinstance(data.get("kind"), str):
        problems.append("transfer record 'kind' must be a string.")
    for field in (
        "to_team",
        "sent_at",
        "storage_condition",
        "sent_by",
        "notes",
    ):
        if data.get(field) is not None and not isinstance(data.get(field), str):
            problems.append(f"transfer record '{field}' must be a string.")
    return problems


def _raise_if_problems(problems: list[str], message: str) -> None:
    if problems:
        raise GatewayError(message, problems)


def _checked(record: dict[str, Any], message: str) -> dict[str, Any]:
    _raise_if_problems(validate_record(record), message)
    return record


def _checked_transfer(
    record: dict[str, Any], message: str
) -> dict[str, Any]:
    _raise_if_problems(validate_transfer_record(record), message)
    return record


def list_samples(conn: Any) -> list[dict[str, Any]]:
    records = store.list_samples(conn)
    for record in records:
        _raise_if_problems(
            validate_record(record),
            "service returned a malformed sample record.",
        )
    return records


def get_sample(conn: Any, sample_id: int) -> dict[str, Any] | None:
    record = store.get_sample(conn, sample_id)
    if record is None:
        return None
    return _checked(record, "service returned a malformed sample record.")


def create_sample(conn: Any, data: dict[str, Any]) -> dict[str, Any]:
    """Create a sample together with its single initial retention transfer
    (README Q7). ``data["retention"]`` carries the storage condition and
    optional sent date / person / notes.
    """
    payload = dict(data)
    if isinstance(payload.get("sample_code"), str):
        payload["sample_code"] = payload["sample_code"].strip().upper()

    retention = payload.pop("retention", None)

    problems = validate_sample(payload)
    if retention is None:
        problems.append(
            "retention is required — every sample gets one initial "
            "in-house transfer."
        )
        retention_data: dict[str, Any] = {}
    elif not isinstance(retention, dict):
        problems.append("retention must be an object.")
        retention_data = {}
    else:
        retention_data = {
            "kind": "retention",
            "to_team": None,
            **retention,
        }
        problems += validate_transfer(retention_data)

    # validate_sample already rejected a malformed code, so the uniqueness
    # query only runs for a well-formed one.
    if not problems and store.sample_code_exists(
        conn, payload["sample_code"]
    ):
        problems.append(
            f"sample_code '{payload['sample_code']}' is already in use."
        )

    if problems:
        raise GatewayError("Cannot create sample.", problems)

    new_id = store.create_sample_with_retention(
        conn, payload, retention_data
    )
    record = store.get_sample(conn, new_id)
    return _checked(record, "service returned a malformed sample record.")


def update_sample(
    conn: Any, sample_id: int, data: dict[str, Any]
) -> dict[str, Any]:
    """Partial update (payload keys merged over the current record).

    Enforces the immutability guard (README Q3/Q11/Q14): sample_code,
    origin and batch_id cannot change after creation.
    """
    current = store.get_sample(conn, sample_id)
    if current is None:
        raise GatewayError(f"Sample {sample_id} not found.")

    problems: list[str] = []
    for field in IMMUTABLE_FIELDS:
        if field in data and data[field] != current[field]:
            problems.append(f"{field} cannot be changed after creation.")
    if problems:
        raise GatewayError("Cannot update sample.", problems)

    merged = {**current, **data}
    problems = validate_sample(merged)
    if problems:
        raise GatewayError("Cannot update sample.", problems)

    store.update_sample(conn, sample_id, merged)
    record = store.get_sample(conn, sample_id)
    return _checked(record, "service returned a malformed sample record.")


def delete_sample(conn: Any, sample_id: int) -> bool:
    """Delete a sample unless it has dispatches or test reports
    (README Q8/Q12). The retention row never blocks.

    Test reports are not implemented yet, so the report condition is a
    placeholder until that module lands.
    """
    current = store.get_sample(conn, sample_id)
    if current is None:
        raise GatewayError(f"Sample {sample_id} not found.")

    dispatches = store.count_transfers(conn, sample_id, kind="dispatch")
    if dispatches:
        noun = "dispatch" if dispatches == 1 else "dispatches"
        raise GatewayError(
            "Cannot delete sample.",
            [
                f"{current['sample_code']} has {dispatches} {noun} "
                "recorded — deletion is blocked while a sample has been "
                "sent to another team (README Q12)."
            ],
        )
    store.delete_sample(conn, sample_id)
    return True


# --- transfers -------------------------------------------------------------

def list_transfers(conn: Any, sample_id: int) -> list[dict[str, Any]]:
    rows = store.list_transfers(conn, sample_id)
    for row in rows:
        _raise_if_problems(
            validate_transfer_record(row),
            "service returned a malformed transfer record.",
        )
    return rows


def create_transfer(
    conn: Any, sample_id: int, data: dict[str, Any]
) -> dict[str, Any]:
    """Add a dispatch transfer (README Q6). A second retention row is
    refused — every sample already has exactly one (Q7)."""
    if store.get_sample(conn, sample_id) is None:
        raise GatewayError(f"Sample {sample_id} not found.")

    problems = validate_transfer(data)
    if data.get("kind") == "retention":
        problems.append(
            "a sample can have only one retention transfer; it is created "
            "with the sample."
        )
    if problems:
        raise GatewayError("Cannot add transfer.", problems)

    transfer_id = store.create_transfer(conn, sample_id, data)
    record = store.get_transfer(conn, transfer_id)
    return _checked_transfer(
        record, "service returned a malformed transfer record."
    )


def update_transfer(
    conn: Any, transfer_id: int, data: dict[str, Any]
) -> dict[str, Any]:
    """Update a dispatch's event fields. The retention row is read-only
    (README Q7)."""
    current = store.get_transfer(conn, transfer_id)
    if current is None:
        raise GatewayError(f"Transfer {transfer_id} not found.")
    if current["kind"] == "retention":
        raise GatewayError(
            "Cannot update transfer.",
            ["the initial retention transfer is read-only (README Q7)."],
        )

    merged = {**current, **data}
    problems = validate_transfer(merged)
    if problems:
        raise GatewayError("Cannot update transfer.", problems)

    store.update_transfer(conn, transfer_id, merged)
    record = store.get_transfer(conn, transfer_id)
    return _checked_transfer(
        record, "service returned a malformed transfer record."
    )


def delete_transfer(conn: Any, transfer_id: int) -> bool:
    """Delete a dispatch. The retention row is non-deletable (README Q7)."""
    current = store.get_transfer(conn, transfer_id)
    if current is None:
        raise GatewayError(f"Transfer {transfer_id} not found.")
    if current["kind"] == "retention":
        raise GatewayError(
            "Cannot delete transfer.",
            ["the initial retention transfer cannot be deleted (README Q7)."],
        )
    store.delete_transfer(conn, transfer_id)
    return True


# --- reverse links (Batches page) ------------------------------------------

_SAMPLE_SUMMARY_FIELDS = ("id", "sample_code", "origin", "status", "taken_at")


def validate_sample_summary(data: dict[str, Any]) -> list[str]:
    """Contract check for a light sample summary row (no heavy fields)."""
    problems: list[str] = []
    missing = [field for field in _SAMPLE_SUMMARY_FIELDS if field not in data]
    if missing:
        problems.append(
            f"sample summary missing fields: {', '.join(missing)}."
        )
    if not isinstance(data.get("id"), int):
        problems.append("sample summary 'id' must be an integer.")
    if not isinstance(data.get("sample_code"), str) or not data.get(
        "sample_code"
    ):
        problems.append(
            "sample summary 'sample_code' must be a non-empty string."
        )
    if not isinstance(data.get("origin"), str):
        problems.append("sample summary 'origin' must be a string.")
    if not isinstance(data.get("status"), str):
        problems.append("sample summary 'status' must be a string.")
    if data.get("taken_at") is not None and not isinstance(
        data.get("taken_at"), str
    ):
        problems.append("sample summary 'taken_at' must be a string.")
    return problems


def list_samples_by_batch(conn: Any, batch_id: int) -> list[dict[str, Any]]:
    """Light summaries of the samples taken from a batch (reverse link)."""
    rows = store.list_samples_by_batch(conn, batch_id)
    for row in rows:
        _raise_if_problems(
            validate_sample_summary(row),
            "service returned a malformed sample summary.",
        )
    return rows


def count_samples_by_batch_id(conn: Any) -> dict[int, int]:
    """{batch_id: sample count} for the Batches overview + delete guard."""
    return store.count_samples_by_batch_id(conn)


def transfer_counts_by_sample_id(conn: Any) -> dict[int, dict[str, int]]:
    """{sample_id: {"total": n, "dispatches": m}} for the Samples overview."""
    return store.transfer_counts_by_sample_id(conn)
