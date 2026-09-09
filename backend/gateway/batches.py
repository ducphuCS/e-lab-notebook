"""Gateway client for the Batches service.

The ONLY code allowed to talk to backend services over HTTP
(docs/TEST_STRATEGIES.md §3). For the v0 prototype
(frontend/batches/README.md §5.2) the transport is in-process: the
gateway calls the SQLite-backed store directly. When a real service
exists, only this module changes (HTTP + JSON); pages keep calling the
same functions.

Gateway duties, applied here:
  1. route to the right service      -> the batches store (in-process)
  2. validate requests before they leave -> ``validate_batch``
  3. validate responses on the way back -> ``validate_record``
  4. uniform error shape             -> ``GatewayError``

Policy guards from the letter live here too (README Q1/Q6):
  - identity fields (batch_code, formula reference + name + version) are
    immutable after creation;
  - ``planned`` is editable only while the batch is still 'planned' (the
    plan is frozen once the run has started);
  - deletion is allowed only while the batch is 'planned'. The second
    delete condition — no linked samples/test reports (Q6) — is a no-op
    until the Samples module exists, exactly like Formulas' placeholder
    stats.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.services.batches import store
from backend.services.batches.schema import BATCH_FIELDS, IMMUTABLE_FIELDS
from backend.services.batches.validation import validate_batch


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
    missing = [field for field in BATCH_FIELDS if field not in data]
    if missing:
        problems.append(
            f"response record missing fields: {', '.join(missing)}."
        )
    if not isinstance(data.get("id"), int):
        problems.append("response record 'id' must be an integer.")
    if not isinstance(data.get("batch_code"), str) or not data.get("batch_code"):
        problems.append("response record 'batch_code' must be a non-empty string.")
    if not isinstance(data.get("name"), str) or not data.get("name"):
        problems.append("response record 'name' must be a non-empty string.")
    if not isinstance(data.get("formula_id"), int):
        problems.append("response record 'formula_id' must be an integer.")
    if not isinstance(data.get("formula_name"), str) or not data.get(
        "formula_name"
    ):
        problems.append(
            "response record 'formula_name' must be a non-empty string."
        )
    if not isinstance(data.get("formula_version"), int):
        problems.append("response record 'formula_version' must be an integer.")
    if not isinstance(data.get("planned"), dict):
        problems.append("response record 'planned' must be an object.")
    actual = data.get("actual")
    if actual is not None and not isinstance(actual, dict):
        problems.append("response record 'actual' must be an object.")
    if not isinstance(data.get("status"), str):
        problems.append("response record 'status' must be a string.")
    for field in ("owner", "created_at", "updated_at"):
        if data.get(field) is not None and not isinstance(data.get(field), str):
            problems.append(f"response record '{field}' must be a string.")
    return problems


def _raise_if_problems(problems: list[str], message: str) -> None:
    if problems:
        raise GatewayError(message, problems)


def _checked(record: dict[str, Any], message: str) -> dict[str, Any]:
    _raise_if_problems(validate_record(record), message)
    return record


def list_batches(conn: Any) -> list[dict[str, Any]]:
    records = store.list_batches(conn)
    for record in records:
        _raise_if_problems(
            validate_record(record),
            "service returned a malformed batch record.",
        )
    return records


def get_batch(conn: Any, batch_id: int) -> dict[str, Any] | None:
    record = store.get_batch(conn, batch_id)
    if record is None:
        return None
    return _checked(record, "service returned a malformed batch record.")


def create_batch(conn: Any, data: dict[str, Any]) -> dict[str, Any]:
    problems = validate_batch(data)
    if problems:
        raise GatewayError("Cannot create batch.", problems)
    new_id = store.create_batch(conn, data)
    record = store.get_batch(conn, new_id)
    return _checked(record, "service returned a malformed batch record.")


def update_batch(
    conn: Any, batch_id: int, data: dict[str, Any]
) -> dict[str, Any]:
    """Partial update (payload keys merged over the current record).

    Enforces the policy guards (README Q1): identity fields cannot change,
    and ``planned`` is frozen once the batch has left 'planned'.
    """
    current = store.get_batch(conn, batch_id)
    if current is None:
        raise GatewayError(f"Batch {batch_id} not found.")

    problems: list[str] = []
    for field in IMMUTABLE_FIELDS:
        if field in data and data[field] != current[field]:
            problems.append(
                f"{field} cannot be changed after creation."
            )
    if (
        "planned" in data
        and data["planned"] != current["planned"]
        and current["status"] != "planned"
    ):
        problems.append(
            "planned cannot be changed once the batch has left 'planned' "
            "status."
        )
    if problems:
        raise GatewayError("Cannot update batch.", problems)

    merged = {**current, **data}
    # actual is a composite (composition/yield/observations) recorded from
    # different editor surfaces on the detail page; merge it sub-key wise so
    # a partial actual update never drops the other parts (README §5.1).
    if isinstance(current.get("actual"), dict) and isinstance(
        data.get("actual"), dict
    ):
        merged["actual"] = {**current["actual"], **data["actual"]}
    problems = validate_batch(merged)
    if problems:
        raise GatewayError("Cannot update batch.", problems)
    store.update_batch(conn, batch_id, merged)
    record = store.get_batch(conn, batch_id)
    return _checked(record, "service returned a malformed batch record.")


def delete_batch(conn: Any, batch_id: int) -> bool:
    """Delete only while the batch is 'planned' (README Q6).

    The second condition — no linked samples/test reports — is a no-op
    until the Samples module lands (the check will be added there).
    """
    current = store.get_batch(conn, batch_id)
    if current is None:
        raise GatewayError(f"Batch {batch_id} not found.")
    if current["status"] != "planned":
        raise GatewayError(
            "Cannot delete batch.",
            [
                f"Only batches still in 'planned' status can be deleted — "
                f"{current['batch_code']} is '{current['status']}'."
            ],
        )
    store.delete_batch(conn, batch_id)
    return True


_BATCH_SUMMARY_FIELDS = (
    "id",
    "batch_code",
    "name",
    "formula_version",
    "status",
    "updated_at",
)


def validate_batch_summary(data: dict[str, Any]) -> list[str]:
    """Contract check for a light batch summary row (no JSON payloads)."""
    problems: list[str] = []
    missing = [field for field in _BATCH_SUMMARY_FIELDS if field not in data]
    if missing:
        problems.append(
            f"batch summary missing fields: {', '.join(missing)}."
        )
    if not isinstance(data.get("id"), int):
        problems.append("batch summary 'id' must be an integer.")
    if not isinstance(data.get("batch_code"), str) or not data.get("batch_code"):
        problems.append("batch summary 'batch_code' must be a non-empty string.")
    if not isinstance(data.get("name"), str):
        problems.append("batch summary 'name' must be a string.")
    if not isinstance(data.get("formula_version"), int):
        problems.append("batch summary 'formula_version' must be an integer.")
    if not isinstance(data.get("status"), str):
        problems.append("batch summary 'status' must be a string.")
    if data.get("updated_at") is not None and not isinstance(
        data.get("updated_at"), str
    ):
        problems.append("batch summary 'updated_at' must be a string.")
    return problems


def list_batches_by_formula(conn: Any, formula_id: int) -> list[dict[str, Any]]:
    """Light summaries of the batches made from a formula (reverse link)."""
    rows = store.list_batches_by_formula(conn, formula_id)
    for row in rows:
        _raise_if_problems(
            validate_batch_summary(row),
            "service returned a malformed batch summary.",
        )
    return rows


def count_batches_by_formula_id(conn: Any) -> dict[int, int]:
    """{formula_id: count} for the Formulas overview column."""
    return store.count_batches_by_formula_id(conn)
