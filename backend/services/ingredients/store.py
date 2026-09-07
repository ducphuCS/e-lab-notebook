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

from backend.services.ingredients.migration import has_legacy_entries, to_new_shape
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


# ---------------------------------------------------------------------------
# TEMP — legacy custom-field migration (remove me).
# See backend/services/ingredients/migration.py and
# frontend/ingredients/README.md §11. The dev DB was migrated by hand;
# these helpers exist for real user DBs created before the custom-field
# unit column (commit 9e1c865, 2026-09-07).
# ---------------------------------------------------------------------------


def _legacy_custom_field_rows(
    conn: sqlite3.Connection,
) -> list[tuple[int, dict[str, Any]]]:
    """(id, decoded custom_fields) for every row still in the legacy shape.

    Rows whose custom_fields column is not valid JSON or not an object are
    skipped: they are corrupt, not legacy, and out of this migration's scope.
    """
    found: list[tuple[int, dict[str, Any]]] = []
    for row in conn.execute("SELECT id, custom_fields FROM ingredients"):
        try:
            fields = json.loads(row["custom_fields"] or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(fields, dict) and has_legacy_entries(fields):
            found.append((int(row["id"]), fields))
    return found


def count_legacy_custom_field_rows(conn: sqlite3.Connection) -> int:
    """How many rows still store custom_fields in the legacy shape.

    Lets the page decide whether to offer the migration button.
    """
    return len(_legacy_custom_field_rows(conn))


def migrate_legacy_custom_fields(conn: sqlite3.Connection) -> int:
    """Rewrite legacy-shaped rows in place; returns the number updated.

    Idempotent — a second call migrates nothing. Values become
    {"value": <text>, "unit": ""}, matching the current shape exactly.
    """
    migrated = 0
    for row_id, fields in _legacy_custom_field_rows(conn):
        conn.execute(
            "UPDATE ingredients SET custom_fields = ? WHERE id = ?",
            (json.dumps(to_new_shape(fields)), row_id),
        )
        migrated += 1
    conn.commit()
    return migrated
