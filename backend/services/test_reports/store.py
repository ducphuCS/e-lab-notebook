"""SQLite-backed test-report store (v0 prototype).

stdlib sqlite3 only. Every function takes an open ``sqlite3.Connection``
so tests can pass an in-memory or temp-file database, and the dev app can
pass a repo-local .db file (frontend/test_reports/README.md §5.3).

The store is deliberately dumb: it does no validation and no policy.
Callers (gateway/page) validate first via ``validation.validate_report`` /
``validate_result``; deletion policy (README Q10 — freely deletable, no
status workflow) lives in the gateway. Cross-service checks (does the
referenced sample/transfer exist?) belong to the page, since samples live
in a different database.

A report and its result rows are separate tables: the report is the
evaluation event, each result is one row per evaluated sample (README §1).
Deleting a report cascades its results in one commit.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.test_reports.schema import (
    TEST_REPORTS_DDL,
    TEST_RESULTS_DDL,
)

# Repo-local dev database (README §5.3). Gitignored via `*.db`.
DEV_DB_PATH = Path(__file__).resolve().parent / "data" / "test_reports.db"

_INSERT_REPORT_SQL = """
INSERT INTO test_reports
    (test_method, evaluation_date, person_in_charge, methodology,
     equipment, panel, notes, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPDATE_REPORT_SQL = """
UPDATE test_reports
SET test_method = ?, evaluation_date = ?, person_in_charge = ?,
    methodology = ?, equipment = ?, panel = ?, notes = ?, updated_at = ?
WHERE id = ?
"""

_INSERT_RESULT_SQL = """
INSERT INTO test_results
    (report_id, sample_id, transfer_id, parameter, value, unit, notes,
     created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPDATE_RESULT_SQL = """
UPDATE test_results
SET sample_id = ?, transfer_id = ?, parameter = ?, value = ?, unit = ?,
    notes = ?, updated_at = ?
WHERE id = ?
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection and ensure the schema exists.

    ``path=None`` -> in-memory database (tests). Otherwise ``path`` is the
    .db file; parent directories are created if missing.
    """
    if path is not None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: Streamlit reruns (and AppTest) can execute
    # the script on different threads than the one that opened the conn.
    conn = sqlite3.connect(
        ":memory:" if path is None else str(path), check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    conn.execute(TEST_REPORTS_DDL)
    conn.execute(TEST_RESULTS_DDL)
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


# --- reports ---------------------------------------------------------------

def list_reports(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """All reports, most recent first (lab-notebook order)."""
    rows = conn.execute(
        "SELECT * FROM test_reports ORDER BY id DESC"
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_report(
    conn: sqlite3.Connection, report_id: int
) -> dict[str, Any] | None:
    """One report by id, or None if it does not exist."""
    row = conn.execute(
        "SELECT * FROM test_reports WHERE id = ?", (report_id,)
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def create_report(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    """Insert a report; returns the new id."""
    now = _now()
    conn.execute(
        _INSERT_REPORT_SQL,
        (
            data.get("test_method"),
            data.get("evaluation_date"),
            data.get("person_in_charge"),
            data.get("methodology"),
            data.get("equipment"),
            data.get("panel"),
            data.get("notes"),
            now,
            now,
        ),
    )
    conn.commit()
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def update_report(
    conn: sqlite3.Connection, report_id: int, data: dict[str, Any]
) -> bool:
    """Update a report (partial merge with the current row).

    Returns False if the report does not exist. The caller validates the
    *merged* record; every header field is mutable (README Q10).
    """
    current = get_report(conn, report_id)
    if current is None:
        return False

    merged = {**current, **data}
    now = _now()
    conn.execute(
        _UPDATE_REPORT_SQL,
        (
            merged.get("test_method"),
            merged.get("evaluation_date"),
            merged.get("person_in_charge"),
            merged.get("methodology"),
            merged.get("equipment"),
            merged.get("panel"),
            merged.get("notes"),
            now,
            report_id,
        ),
    )
    conn.commit()
    return True


def delete_report(conn: sqlite3.Connection, report_id: int) -> bool:
    """Delete a report and its results; False if it did not exist.

    No policy here — README Q10 makes a report freely deletable; the page
    asks for confirmation first.
    """
    conn.execute(
        "DELETE FROM test_results WHERE report_id = ?", (report_id,)
    )
    cursor = conn.execute(
        "DELETE FROM test_reports WHERE id = ?", (report_id,)
    )
    conn.commit()
    return cursor.rowcount > 0


# --- results ---------------------------------------------------------------

def list_results(
    conn: sqlite3.Connection, report_id: int
) -> list[dict[str, Any]]:
    """A report's result rows, in insertion order (README §4 Results tab)."""
    rows = conn.execute(
        "SELECT * FROM test_results WHERE report_id = ? ORDER BY id",
        (report_id,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_result(
    conn: sqlite3.Connection, result_id: int
) -> dict[str, Any] | None:
    """One result by id, or None if it does not exist."""
    row = conn.execute(
        "SELECT * FROM test_results WHERE id = ?", (result_id,)
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def create_result(
    conn: sqlite3.Connection, report_id: int, data: dict[str, Any]
) -> int:
    """Insert one result row for a report; returns the new id."""
    now = _now()
    conn.execute(
        _INSERT_RESULT_SQL,
        (
            report_id,
            data.get("sample_id"),
            data.get("transfer_id"),
            data.get("parameter"),
            data.get("value"),
            data.get("unit"),
            data.get("notes"),
            now,
            now,
        ),
    )
    conn.commit()
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def update_result(
    conn: sqlite3.Connection, result_id: int, data: dict[str, Any]
) -> bool:
    """Update a result (partial merge with the current row).

    Returns False if the result does not exist. ``report_id`` is never
    rewritten by an update — a result stays in its report.
    """
    current = get_result(conn, result_id)
    if current is None:
        return False

    merged = {**current, **data}
    now = _now()
    conn.execute(
        _UPDATE_RESULT_SQL,
        (
            merged.get("sample_id"),
            merged.get("transfer_id"),
            merged.get("parameter"),
            merged.get("value"),
            merged.get("unit"),
            merged.get("notes"),
            now,
            result_id,
        ),
    )
    conn.commit()
    return True


def delete_result(conn: sqlite3.Connection, result_id: int) -> bool:
    """Delete one result row; False if it did not exist."""
    cursor = conn.execute(
        "DELETE FROM test_results WHERE id = ?", (result_id,)
    )
    conn.commit()
    return cursor.rowcount > 0


# --- reverse links (Samples / Batches pages) -------------------------------

def result_stats_by_report_id(
    conn: sqlite3.Connection,
) -> dict[int, dict[str, int]]:
    """{report_id: {"results": n, "samples": m}} — one GROUP BY query,
    so the Test Reports overview can fill its sample/result columns in a
    single call. ``samples`` counts distinct samples (a report may carry
    replicates for the same sample).
    """
    rows = conn.execute(
        "SELECT report_id, COUNT(*) AS results, "
        "       COUNT(DISTINCT sample_id) AS samples "
        "FROM test_results GROUP BY report_id"
    ).fetchall()
    return {
        int(row["report_id"]): {
            "results": int(row["results"]),
            "samples": int(row["samples"]),
        }
        for row in rows
    }


def count_reports_by_sample_id(
    conn: sqlite3.Connection,
) -> dict[int, int]:
    """{sample_id: distinct report count} — one GROUP BY query, so the
    Samples overview can fill its test-report column in a single call.

    Distinct reports, not result rows: a sample with replicates in one
    report still counts as one report (README §5.2).
    """
    rows = conn.execute(
        "SELECT sample_id, COUNT(DISTINCT report_id) AS n "
        "FROM test_results GROUP BY sample_id"
    ).fetchall()
    return {int(row["sample_id"]): int(row["n"]) for row in rows}


def count_reports_by_sample_ids(
    conn: sqlite3.Connection, sample_ids: list[int]
) -> int:
    """Distinct report count across a set of samples (Batches page).

    A report covering several samples of one batch is counted once.
    """
    ids = [int(sample_id) for sample_id in sample_ids]
    if not ids:
        return 0
    placeholders = ", ".join("?" for _ in ids)
    row = conn.execute(
        f"SELECT COUNT(DISTINCT report_id) AS n FROM test_results "
        f"WHERE sample_id IN ({placeholders})",
        ids,
    ).fetchone()
    return int(row["n"])


def count_results_by_transfer_id(
    conn: sqlite3.Connection, transfer_id: int
) -> int:
    """How many result rows reference a transfer.

    The Samples page uses this to pin a transfer against deletion while a
    result anchors to it (README Q11).
    """
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM test_results WHERE transfer_id = ?",
        (transfer_id,),
    ).fetchone()
    return int(row["n"])


def list_results_by_sample(
    conn: sqlite3.Connection, sample_id: int
) -> list[dict[str, Any]]:
    """Light result rows for one sample, joined with report info (README
    §6 Samples reverse link): id, report_id, test_method, evaluation_date,
    parameter, value, unit, transfer_id. Heaviest fields (notes) omitted.

    Serves the Samples detail Test reports tab; newest evaluation first.
    """
    rows = conn.execute(
        "SELECT r.id, r.report_id, tr.test_method, tr.evaluation_date, "
        "       r.parameter, r.value, r.unit, r.transfer_id "
        "FROM test_results r "
        "JOIN test_reports tr ON tr.id = r.report_id "
        "WHERE r.sample_id = ? "
        "ORDER BY tr.evaluation_date DESC, r.id DESC",
        (sample_id,),
    ).fetchall()
    return [dict(row) for row in rows]
