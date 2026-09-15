"""SQLite-backed sample store (v0 prototype).

stdlib sqlite3 only. Every function takes an open ``sqlite3.Connection``
so tests can pass an in-memory or temp-file database, and the dev app can
pass a repo-local .db file (frontend/samples/README.md §5.2).

The store is deliberately dumb: it does no validation and no policy.
Callers (gateway/page) validate first via ``validation.validate_sample`` /
``validate_transfer``; policy guards (the retention invariant, immutable
identity, the delete guard) live in the gateway (README Q7/Q8/Q11/Q12).

``create_sample_with_retention`` inserts the sample and its one retention
transfer in a single commit, so the "exactly one retention row per sample"
invariant (README Q7) holds even if a later transfer insert fails.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.samples.schema import (
    SAMPLE_TRANSFERS_DDL,
    SAMPLES_DDL,
)

# Repo-local dev database (README §5.2). Gitignored via `*.db`.
DEV_DB_PATH = Path(__file__).resolve().parent / "data" / "samples.db"

_INSERT_SAMPLE_SQL = """
INSERT INTO samples
    (sample_code, origin, batch_id, source, taken_at, status, notes,
     created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

# Mutable sample columns only — identity and provenance are pinned at
# creation (README Q3/Q11/Q14) and are never written here.
_UPDATE_SAMPLE_SQL = """
UPDATE samples
SET source = ?, taken_at = ?, status = ?, notes = ?, updated_at = ?
WHERE id = ?
"""

_INSERT_TRANSFER_SQL = """
INSERT INTO sample_transfers
    (sample_id, kind, to_team, sent_at, storage_condition, sent_by, notes)
VALUES (?, ?, ?, ?, ?, ?, ?)
"""

# Mutable transfer columns only — kind is fixed for a row's life (the
# retention row is read-only; README Q7).
_UPDATE_TRANSFER_SQL = """
UPDATE sample_transfers
SET to_team = ?, sent_at = ?, storage_condition = ?, sent_by = ?, notes = ?
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
    conn.execute(SAMPLES_DDL)
    conn.execute(SAMPLE_TRANSFERS_DDL)
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


# --- samples ---------------------------------------------------------------

def list_samples(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """All samples, most recent first (lab-notebook order)."""
    rows = conn.execute("SELECT * FROM samples ORDER BY id DESC").fetchall()
    return [_row_to_dict(row) for row in rows]


def get_sample(
    conn: sqlite3.Connection, sample_id: int
) -> dict[str, Any] | None:
    """One sample by id, or None if it does not exist."""
    row = conn.execute(
        "SELECT * FROM samples WHERE id = ?", (sample_id,)
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def sample_code_exists(conn: sqlite3.Connection, code: str) -> bool:
    """Case-insensitive lookup of a sample code (README Q11)."""
    row = conn.execute(
        "SELECT 1 FROM samples WHERE UPPER(sample_code) = UPPER(?)",
        (code,),
    ).fetchone()
    return row is not None


def create_sample_with_retention(
    conn: sqlite3.Connection,
    data: dict[str, Any],
    retention: dict[str, Any],
) -> int:
    """Insert a sample and its initial retention transfer; returns the id.

    Both rows are inserted before a single commit (README Q7: exactly one
    retention row per sample).
    """
    now = _now()
    conn.execute(
        _INSERT_SAMPLE_SQL,
        (
            data.get("sample_code"),
            data.get("origin") or "batch",
            data.get("batch_id"),
            data.get("source"),
            data.get("taken_at"),
            data.get("status") or "active",
            data.get("notes"),
            now,
            now,
        ),
    )
    sample_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    conn.execute(
        _INSERT_TRANSFER_SQL,
        (
            sample_id,
            "retention",
            None,
            retention.get("sent_at") or data.get("taken_at"),
            retention.get("storage_condition"),
            retention.get("sent_by"),
            retention.get("notes"),
        ),
    )
    conn.commit()
    return sample_id


def update_sample(
    conn: sqlite3.Connection, sample_id: int, data: dict[str, Any]
) -> bool:
    """Update a sample (partial merge with the current row).

    Returns False if the sample does not exist. Only the mutable columns
    are written (see ``_UPDATE_SAMPLE_SQL``), so identity and provenance
    can never drift even if a caller slips extra keys through. The caller
    validates the *merged* record and enforces the immutability guard
    (gateway).
    """
    current = get_sample(conn, sample_id)
    if current is None:
        return False

    merged = {**current, **data}
    now = _now()
    conn.execute(
        _UPDATE_SAMPLE_SQL,
        (
            merged.get("source"),
            merged.get("taken_at"),
            merged.get("status") or "active",
            merged.get("notes"),
            now,
            sample_id,
        ),
    )
    conn.commit()
    return True


def delete_sample(conn: sqlite3.Connection, sample_id: int) -> bool:
    """Delete a sample and its transfers; False if it did not exist.

    No policy here — whether deletion is allowed (no dispatches / test
    reports, README Q8/Q12) is decided by the gateway before calling.
    """
    conn.execute(
        "DELETE FROM sample_transfers WHERE sample_id = ?", (sample_id,)
    )
    cursor = conn.execute("DELETE FROM samples WHERE id = ?", (sample_id,))
    conn.commit()
    return cursor.rowcount > 0


# --- transfers -------------------------------------------------------------

def list_transfers(
    conn: sqlite3.Connection, sample_id: int
) -> list[dict[str, Any]]:
    """A sample's transfers, newest first (README §4 Transfers tab).

    Ordered by sent date then insertion id, so dispatches generally sit
    above the older retention row.
    """
    rows = conn.execute(
        "SELECT * FROM sample_transfers WHERE sample_id = ? "
        "ORDER BY sent_at DESC, id DESC",
        (sample_id,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_transfer(
    conn: sqlite3.Connection, transfer_id: int
) -> dict[str, Any] | None:
    """One transfer by id, or None if it does not exist."""
    row = conn.execute(
        "SELECT * FROM sample_transfers WHERE id = ?", (transfer_id,)
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def create_transfer(
    conn: sqlite3.Connection, sample_id: int, data: dict[str, Any]
) -> int:
    """Insert one transfer for a sample; returns the new id."""
    conn.execute(
        _INSERT_TRANSFER_SQL,
        (
            sample_id,
            data.get("kind") or "dispatch",
            data.get("to_team"),
            data.get("sent_at"),
            data.get("storage_condition"),
            data.get("sent_by"),
            data.get("notes"),
        ),
    )
    conn.commit()
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def update_transfer(
    conn: sqlite3.Connection, transfer_id: int, data: dict[str, Any]
) -> bool:
    """Update a transfer's event fields; False if it does not exist.

    ``kind`` is never rewritten by an update.
    """
    current = get_transfer(conn, transfer_id)
    if current is None:
        return False
    merged = {**current, **data}
    conn.execute(
        _UPDATE_TRANSFER_SQL,
        (
            merged.get("to_team"),
            merged.get("sent_at"),
            merged.get("storage_condition"),
            merged.get("sent_by"),
            merged.get("notes"),
            transfer_id,
        ),
    )
    conn.commit()
    return True


def delete_transfer(conn: sqlite3.Connection, transfer_id: int) -> bool:
    """Delete a transfer; False if it did not exist (policy in gateway)."""
    cursor = conn.execute(
        "DELETE FROM sample_transfers WHERE id = ?", (transfer_id,)
    )
    conn.commit()
    return cursor.rowcount > 0


def count_transfers(
    conn: sqlite3.Connection, sample_id: int, kind: str | None = None
) -> int:
    """Count a sample's transfers, optionally filtered by kind."""
    if kind is None:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM sample_transfers WHERE sample_id = ?",
            (sample_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM sample_transfers "
            "WHERE sample_id = ? AND kind = ?",
            (sample_id, kind),
        ).fetchone()
    return int(row["n"])


# --- reverse links (Batches page) ------------------------------------------

def list_samples_by_batch(
    conn: sqlite3.Connection, batch_id: int
) -> list[dict[str, Any]]:
    """Light summaries of the samples taken from a batch (most recent
    first): id, sample_code, origin, status, taken_at. No heavy fields.

    Serves the Batches detail Samples tab and delete guard (README §6).
    """
    rows = conn.execute(
        "SELECT id, sample_code, origin, status, taken_at "
        "FROM samples WHERE batch_id = ? ORDER BY id DESC",
        (batch_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def count_samples_by_batch_id(
    conn: sqlite3.Connection,
) -> dict[int, int]:
    """{batch_id: sample count} across batch-born samples — one GROUP BY
    query, so the Batches overview can fill its samples column in a single
    call.
    """
    rows = conn.execute(
        "SELECT batch_id, COUNT(*) AS n FROM samples "
        "WHERE batch_id IS NOT NULL GROUP BY batch_id"
    ).fetchall()
    return {int(row["batch_id"]): int(row["n"]) for row in rows}


def transfer_counts_by_sample_id(
    conn: sqlite3.Connection,
) -> dict[int, dict[str, int]]:
    """{sample_id: {"total": n, "dispatches": m}} — one GROUP BY query, so
    the Samples overview can fill its dispatch column in a single call
    (README §4/Q13). The retention row counts toward ``total`` but never
    toward ``dispatches``.
    """
    rows = conn.execute(
        "SELECT sample_id, "
        "       COUNT(*) AS total, "
        "       SUM(CASE WHEN kind = 'dispatch' THEN 1 ELSE 0 END) AS dispatches "
        "FROM sample_transfers GROUP BY sample_id"
    ).fetchall()
    return {
        int(row["sample_id"]): {
            "total": int(row["total"]),
            "dispatches": int(row["dispatches"] or 0),
        }
        for row in rows
    }
