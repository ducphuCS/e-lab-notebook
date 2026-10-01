"""Gateway client for the Test Reports service.

The ONLY code allowed to talk to backend services over HTTP
(docs/TEST_STRATEGIES.md §3). For the v0 prototype
(frontend/test_reports/README.md §5.3) the transport is in-process: the
gateway calls the SQLite-backed store directly. When a real service
exists, only this module changes (HTTP + JSON); pages keep calling the
same functions.

Gateway duties, applied here:
  1. route to the right service      -> the test_reports store (in-process)
  2. validate requests before they leave -> ``validate_report`` /
     ``validate_result``
  3. validate responses on the way back -> ``validate_report_record`` /
     ``validate_result_record`` / ``validate_result_summary``
  4. uniform error shape             -> ``GatewayError``

Policy from the letter lives here too: a result is validated against its
parent report (the report must exist); a report is freely editable and
deletable, cascading its results (README Q10). Whether a referenced
sample/transfer exists is a cross-service concern the page owns.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.services.test_reports import store
from backend.services.test_reports.schema import REPORT_FIELDS, RESULT_FIELDS
from backend.services.test_reports.validation import (
    validate_report,
    validate_result,
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


def validate_report_record(data: dict[str, Any]) -> list[str]:
    """Contract enforcement: check a service report record's shape.

    Pure and public so contract tests can feed golden JSON fixtures
    directly (tests/contracts/).
    """
    problems: list[str] = []
    missing = [field for field in REPORT_FIELDS if field not in data]
    if missing:
        problems.append(
            f"response record missing fields: {', '.join(missing)}."
        )
    if not isinstance(data.get("id"), int):
        problems.append("response record 'id' must be an integer.")
    if not isinstance(data.get("test_method"), str) or not data.get(
        "test_method"
    ):
        problems.append(
            "response record 'test_method' must be a non-empty string."
        )
    if not isinstance(data.get("evaluation_date"), str):
        problems.append(
            "response record 'evaluation_date' must be a string."
        )
    for field in (
        "person_in_charge",
        "methodology",
        "equipment",
        "panel",
        "notes",
        "created_at",
        "updated_at",
    ):
        if data.get(field) is not None and not isinstance(data.get(field), str):
            problems.append(f"response record '{field}' must be a string.")
    return problems


def validate_result_record(data: dict[str, Any]) -> list[str]:
    """Contract check for a result response record."""
    problems: list[str] = []
    missing = [field for field in RESULT_FIELDS if field not in data]
    if missing:
        problems.append(
            f"result record missing fields: {', '.join(missing)}."
        )
    for field in ("id", "report_id", "sample_id", "transfer_id"):
        if not isinstance(data.get(field), int):
            problems.append(f"result record '{field}' must be an integer.")
    if not isinstance(data.get("parameter"), str) or not data.get(
        "parameter"
    ):
        problems.append(
            "result record 'parameter' must be a non-empty string."
        )
    value = data.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        problems.append("result record 'value' must be a number.")
    for field in ("unit", "notes", "created_at", "updated_at"):
        if data.get(field) is not None and not isinstance(data.get(field), str):
            problems.append(f"result record '{field}' must be a string.")
    return problems


_RESULT_SUMMARY_FIELDS = (
    "id",
    "report_id",
    "test_method",
    "evaluation_date",
    "parameter",
    "value",
    "unit",
    "transfer_id",
)


def validate_result_summary(data: dict[str, Any]) -> list[str]:
    """Contract check for a light result summary row (reverse link)."""
    problems: list[str] = []
    missing = [
        field for field in _RESULT_SUMMARY_FIELDS if field not in data
    ]
    if missing:
        problems.append(
            f"result summary missing fields: {', '.join(missing)}."
        )
    for field in ("id", "report_id", "transfer_id"):
        if not isinstance(data.get(field), int):
            problems.append(f"result summary '{field}' must be an integer.")
    for field in ("test_method", "evaluation_date", "parameter"):
        if not isinstance(data.get(field), str) or not data.get(field):
            problems.append(
                f"result summary '{field}' must be a non-empty string."
            )
    value = data.get("value")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        problems.append("result summary 'value' must be a number.")
    if data.get("unit") is not None and not isinstance(data.get("unit"), str):
        problems.append("result summary 'unit' must be a string.")
    return problems


def _raise_if_problems(problems: list[str], message: str) -> None:
    if problems:
        raise GatewayError(message, problems)


def _checked(record: dict[str, Any], message: str) -> dict[str, Any]:
    _raise_if_problems(validate_report_record(record), message)
    return record


def _checked_result(
    record: dict[str, Any], message: str
) -> dict[str, Any]:
    _raise_if_problems(validate_result_record(record), message)
    return record


def _checked_summary(
    record: dict[str, Any], message: str
) -> dict[str, Any]:
    _raise_if_problems(validate_result_summary(record), message)
    return record


# --- reports ---------------------------------------------------------------

def list_reports(conn: Any) -> list[dict[str, Any]]:
    records = store.list_reports(conn)
    for record in records:
        _raise_if_problems(
            validate_report_record(record),
            "service returned a malformed report record.",
        )
    return records


def get_report(conn: Any, report_id: int) -> dict[str, Any] | None:
    record = store.get_report(conn, report_id)
    if record is None:
        return None
    return _checked(record, "service returned a malformed report record.")


def create_report(conn: Any, data: dict[str, Any]) -> dict[str, Any]:
    """Create a report header (README Q15: header first, results follow)."""
    payload = dict(data)
    problems = validate_report(payload)
    if problems:
        raise GatewayError("Cannot create report.", problems)

    report_id = store.create_report(conn, payload)
    record = store.get_report(conn, report_id)
    return _checked(record, "service returned a malformed report record.")


def update_report(
    conn: Any, report_id: int, data: dict[str, Any]
) -> dict[str, Any]:
    """Partial update (payload keys merged over the current record).

    Every header field is editable in v0 (README Q10).
    """
    current = store.get_report(conn, report_id)
    if current is None:
        raise GatewayError(f"Report {report_id} not found.")

    merged = {**current, **data}
    problems = validate_report(merged)
    if problems:
        raise GatewayError("Cannot update report.", problems)

    store.update_report(conn, report_id, merged)
    record = store.get_report(conn, report_id)
    return _checked(record, "service returned a malformed report record.")


def delete_report(conn: Any, report_id: int) -> bool:
    """Delete a report and its results (README Q10)."""
    if store.get_report(conn, report_id) is None:
        raise GatewayError(f"Report {report_id} not found.")
    store.delete_report(conn, report_id)
    return True


# --- results ---------------------------------------------------------------

def list_results(conn: Any, report_id: int) -> list[dict[str, Any]]:
    rows = store.list_results(conn, report_id)
    for row in rows:
        _raise_if_problems(
            validate_result_record(row),
            "service returned a malformed result record.",
        )
    return rows


def get_result(conn: Any, result_id: int) -> dict[str, Any] | None:
    record = store.get_result(conn, result_id)
    if record is None:
        return None
    return _checked_result(
        record, "service returned a malformed result record."
    )


def create_result(
    conn: Any, report_id: int, data: dict[str, Any]
) -> dict[str, Any]:
    """Add one result row (one evaluated sample) to a report (README Q6).

    The report must exist; the referenced sample/transfer are validated by
    the page (they live in the samples service).
    """
    if store.get_report(conn, report_id) is None:
        raise GatewayError(f"Report {report_id} not found.")

    payload = {"report_id": report_id, **data}
    problems = validate_result(payload)
    if problems:
        raise GatewayError("Cannot add result.", problems)

    result_id = store.create_result(conn, report_id, payload)
    record = store.get_result(conn, result_id)
    return _checked_result(
        record, "service returned a malformed result record."
    )


def update_result(
    conn: Any, result_id: int, data: dict[str, Any]
) -> dict[str, Any]:
    """Partial update of a result row. ``report_id`` cannot change."""
    current = store.get_result(conn, result_id)
    if current is None:
        raise GatewayError(f"Result {result_id} not found.")

    merged = {**current, **data}
    merged["report_id"] = current["report_id"]
    problems = validate_result(merged)
    if problems:
        raise GatewayError("Cannot update result.", problems)

    store.update_result(conn, result_id, merged)
    record = store.get_result(conn, result_id)
    return _checked_result(
        record, "service returned a malformed result record."
    )


def delete_result(conn: Any, result_id: int) -> bool:
    """Delete one result row; False if it did not exist."""
    if store.get_result(conn, result_id) is None:
        raise GatewayError(f"Result {result_id} not found.")
    store.delete_result(conn, result_id)
    return True


# --- reverse links (Samples / Batches pages) -------------------------------

def result_stats_by_report_id(conn: Any) -> dict[int, dict[str, int]]:
    """{report_id: {"results": n, "samples": m}} for the overview."""
    return store.result_stats_by_report_id(conn)


def count_reports_by_sample_id(conn: Any) -> dict[int, int]:
    """{sample_id: distinct report count} for the Samples overview."""
    return store.count_reports_by_sample_id(conn)


def count_reports_by_sample_ids(conn: Any, sample_ids: list[int]) -> int:
    """Distinct report count across a set of samples (Batches page)."""
    return store.count_reports_by_sample_ids(conn, sample_ids)


def count_results_by_transfer_id(conn: Any, transfer_id: int) -> int:
    """How many result rows reference a transfer (Samples transfer pin)."""
    return store.count_results_by_transfer_id(conn, transfer_id)


def list_results_by_sample(
    conn: Any, sample_id: int
) -> list[dict[str, Any]]:
    """Light result summaries for a sample (Samples detail tab)."""
    rows = store.list_results_by_sample(conn, sample_id)
    for row in rows:
        _raise_if_problems(
            validate_result_summary(row),
            "service returned a malformed result summary.",
        )
    return rows
