"""SQLite-backed ingredient store (v0 prototype).

stdlib sqlite3 only. Every function takes an open ``sqlite3.Connection``
so tests can pass an in-memory or temp-file database (tests/_scratch/),
and the dev app can pass a repo-local .db file (README §5.2).

The store is deliberately dumb: it does no validation. Callers
(gateway/page) validate first via ``validation.validate_ingredient``.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from backend.services.ingredients.schema import INGREDIENTS_DDL

# Repo-local dev database (README §5.2). Gitignored via `*.db` (step 5 of
# the implementation plan; root .gitignore edit pending owner approval).
DEV_DB_PATH = Path(__file__).resolve().parent / "data" / "ingredients.db"

_INSERT_SQL = """
INSERT INTO ingredients
    (name, item_code, item_description, supplier, notes, uom, state, custom_fields)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPDATE_SQL = """
UPDATE ingredients
SET name = ?, item_code = ?, item_description = ?, supplier = ?, notes = ?,
    uom = ?, state = ?, custom_fields = ?
WHERE id = ?
"""


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
    conn.execute(INGREDIENTS_DDL)
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["custom_fields"] = json.loads(data["custom_fields"] or "{}")
    return data


def list_ingredients(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """All ingredients, ordered by name."""
    rows = conn.execute("SELECT * FROM ingredients ORDER BY name").fetchall()
    return [_row_to_dict(row) for row in rows]


def get_ingredient(
    conn: sqlite3.Connection, ingredient_id: int
) -> dict[str, Any] | None:
    """One ingredient by id, or None if it does not exist."""
    row = conn.execute(
        "SELECT * FROM ingredients WHERE id = ?", (ingredient_id,)
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def create_ingredient(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    """Insert an ingredient; returns the new row id."""
    conn.execute(
        _INSERT_SQL,
        (
            data.get("name"),
            data.get("item_code"),
            data.get("item_description"),
            data.get("supplier"),
            data.get("notes"),
            data.get("uom"),
            data.get("state"),
            json.dumps(data.get("custom_fields") or {}),
        ),
    )
    conn.commit()
    return int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def update_ingredient(
    conn: sqlite3.Connection, ingredient_id: int, data: dict[str, Any]
) -> bool:
    """Update an ingredient (partial merge with the current row).

    Returns False if the ingredient does not exist. The caller is
    responsible for validating the *merged* record before calling.
    """
    current = get_ingredient(conn, ingredient_id)
    if current is None:
        return False
    merged = {**current, **data}
    merged.pop("id", None)
    conn.execute(
        _UPDATE_SQL,
        (
            merged.get("name"),
            merged.get("item_code"),
            merged.get("item_description"),
            merged.get("supplier"),
            merged.get("notes"),
            merged.get("uom"),
            merged.get("state"),
            json.dumps(merged.get("custom_fields") or {}),
            ingredient_id,
        ),
    )
    conn.commit()
    return True


def delete_ingredient(conn: sqlite3.Connection, ingredient_id: int) -> bool:
    """Delete an ingredient; returns False if it did not exist."""
    cursor = conn.execute(
        "DELETE FROM ingredients WHERE id = ?", (ingredient_id,)
    )
    conn.commit()
    return cursor.rowcount > 0
