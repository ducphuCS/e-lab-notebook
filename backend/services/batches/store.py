"""SQLite-backed batch store (v0 prototype).

stdlib sqlite3 only. Every function takes an open ``sqlite3.Connection``
so tests can pass an in-memory or temp-file database, and the dev app can
pass a repo-local .db file (frontend/batches/README.md §5.2).

Batch codes (README Q4): the store auto-generates ``B-####`` at creation
from a monotonic counter (``batch_seq``), so codes are never reused even
when a 'planned' batch is deleted. Identity fields (batch_code, formula
reference + name + version) are set once at creation and never rewritten
by updates.

The store is deliberately dumb: it does no validation and no policy.
Callers (gateway/page) validate first via ``validation.validate_batch``;
policy guards (delete only while 'planned', plan frozen once the batch
has left 'planned') live in the gateway (README Q1/Q6).
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.batches.schema import BATCHES_DDL, BATCH_SEQ_DDL

# Repo-local dev database (README §5.2). Gitignored via `*.db`.
DEV_DB_PATH = Path(__file__).resolve().parent / "data" / "batches.db"

_INSERT_SQL = """
INSERT INTO batches
    (batch_code, name, formula_id, formula_name, formula_version,
     planned, actual, status, owner, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

# Mutable columns only — identity and the formula reference are pinned at
# creation (README Q1) and are never written here.
_UPDATE_SQL = """
UPDATE batches
SET name = ?, planned = ?, actual = ?, status = ?, owner = ?, updated_at = ?
WHERE id = ?
"""

_JSON_FIELDS = ("planned", "actual")


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
    conn.execute(BATCHES_DDL)
    conn.execute(BATCH_SEQ_DDL)
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    for field in _JSON_FIELDS:
        data[field] = json.loads(data[field] or "{}")
    return data


def _next_batch_code(conn: sqlite3.Connection) -> str:
    """Next sequential code ``B-####`` from the monotonic counter."""
    conn.execute("INSERT OR IGNORE INTO batch_seq (id, next_val) VALUES (1, 1)")
    row = conn.execute(
        "SELECT next_val FROM batch_seq WHERE id = 1"
    ).fetchone()
    n = int(row["next_val"])
    conn.execute(
        "UPDATE batch_seq SET next_val = next_val + 1 WHERE id = 1"
    )
    return f"B-{n:04d}"


def list_batches(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """All batches, most recent first (lab-notebook order)."""
    rows = conn.execute("SELECT * FROM batches ORDER BY id DESC").fetchall()
    return [_row_to_dict(row) for row in rows]


def get_batch(
    conn: sqlite3.Connection, batch_id: int
) -> dict[str, Any] | None:
    """One batch by id, or None if it does not exist."""
    row = conn.execute(
        "SELECT * FROM batches WHERE id = ?", (batch_id,)
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def create_batch(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    """Insert a batch (new sequential code, status defaults to 'planned').

    Returns the new id. ``planned`` is required; ``actual`` defaults to {}.
    """
    now = _now()
    conn.execute(
        _INSERT_SQL,
        (
            _next_batch_code(conn),
            data.get("name"),
            data.get("formula_id"),
            data.get("formula_name"),
            data.get("formula_version"),
            json.dumps(data.get("planned") or {}),
            json.dumps(data.get("actual") or {}),
            data.get("status") or "planned",
            data.get("owner"),
            now,
            now,
        ),
    )
    conn.commit()
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def update_batch(
    conn: sqlite3.Connection, batch_id: int, data: dict[str, Any]
) -> bool:
    """Update a batch (partial merge with the current row).

    Returns False if the batch does not exist. Only the mutable columns are
    written (see ``_UPDATE_SQL``), so identity fields can never drift even
    if a caller slips extra keys through. The caller is responsible for
    validating the *merged* record and for policy guards (gateway).
    """
    current = get_batch(conn, batch_id)
    if current is None:
        return False

    merged = {**current, **data}
    merged.pop("id", None)
    merged.pop("created_at", None)
    now = _now()
    merged["updated_at"] = now

    conn.execute(
        _UPDATE_SQL,
        (
            merged.get("name"),
            json.dumps(merged.get("planned") or {}),
            json.dumps(merged.get("actual") or {}),
            merged.get("status") or "planned",
            merged.get("owner"),
            now,
            batch_id,
        ),
    )
    conn.commit()
    return True


def delete_batch(conn: sqlite3.Connection, batch_id: int) -> bool:
    """Delete a batch; False if it did not exist.

    No policy here — whether deletion is allowed (only while 'planned',
    README Q6) is decided by the gateway before calling.
    """
    cursor = conn.execute("DELETE FROM batches WHERE id = ?", (batch_id,))
    conn.commit()
    return cursor.rowcount > 0


def list_batches_by_formula(
    conn: sqlite3.Connection, formula_id: int
) -> list[dict[str, Any]]:
    """Light summary rows of the batches made from a formula (most recent
    first): id, batch_code, name, formula_version, status, updated_at —
    no JSON payloads. formula_version is the version the batch pinned at
    creation, so the related-batches list can show which revision of the
    formula each batch was made from.

    Serves the Formulas page's reverse link (that letter's §6): the
    related-batches list on the formula detail and the delete guard.
    """
    rows = conn.execute(
        "SELECT id, batch_code, name, formula_version, status, updated_at "
        "FROM batches WHERE formula_id = ? ORDER BY id DESC",
        (formula_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def count_batches_by_formula_id(conn: sqlite3.Connection) -> dict[int, int]:
    """{formula_id: batch count} across all batches — one GROUP BY query,
    so the Formulas overview can fill its batches column in a single call.
    """
    rows = conn.execute(
        "SELECT formula_id, COUNT(*) AS n FROM batches GROUP BY formula_id"
    ).fetchall()
    return {int(row["formula_id"]): int(row["n"]) for row in rows}
