"""SQLite-backed formula store (v0 prototype).

stdlib sqlite3 only. Every function takes an open ``sqlite3.Connection``
so tests can pass an in-memory or temp-file database, and the dev app can
pass a repo-local .db file (README §5.2).

Versioning (README Q2): a new version is created only when the composition
changes; the snapshot table stores the full formula record at that moment.
Status/name-only edits update the current record in place and never bump
the version.

The store is deliberately dumb: it does no validation. Callers
(gateway/page) validate first via ``validation.validate_formula``.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.formulas.schema import FORMULA_VERSIONS_DDL, FORMULAS_DDL

# Repo-local dev database (README §5.2). Gitignored via `*.db`.
DEV_DB_PATH = Path(__file__).resolve().parent / "data" / "formulas.db"

_INSERT_SQL = """
INSERT INTO formulas
    (name, project, status, family, owner, tags, description, custom_fields,
     composition, params, procedure, version, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPDATE_SQL = """
UPDATE formulas
SET name = ?, project = ?, status = ?, family = ?, owner = ?, tags = ?,
    description = ?, custom_fields = ?, composition = ?, params = ?,
    procedure = ?, version = ?, updated_at = ?
WHERE id = ?
"""

_JSON_FIELDS = ("tags", "custom_fields", "composition", "params", "procedure")

# Content fields copied by duplicate_formula (README §3 user flow).
_CONTENT_FIELDS = (
    "name", "project", "status", "family", "owner", "tags", "description",
    "custom_fields", "composition", "params", "procedure",
)


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
    conn.execute(FORMULAS_DDL)
    conn.execute(FORMULA_VERSIONS_DDL)
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    for field in _JSON_FIELDS:
        raw = data[field]
        fallback = "{}" if field == "custom_fields" else "[]"
        data[field] = json.loads(raw or fallback)
    return data


def list_formulas(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """All formulas, ordered by name."""
    rows = conn.execute("SELECT * FROM formulas ORDER BY name").fetchall()
    return [_row_to_dict(row) for row in rows]


def count_formulas_by_ingredient_id(
    conn: sqlite3.Connection,
) -> dict[int, int]:
    """{ingredient_id: formula count} from current compositions.

    Serves the Ingredients page's reverse link
    (frontend/ingredients/README.md §6): how many formulas reference an
    ingredient. Composition rows are stored as JSON, so this mirrors the
    Batches ``count_batches_by_formula_id`` with a parse instead of a
    single GROUP BY. A formula counts once per ingredient even when the
    ingredient appears in several composition rows; historical
    ``formula_versions`` snapshots are ignored (not live references).
    """
    counts: dict[int, int] = {}
    rows = conn.execute("SELECT composition FROM formulas").fetchall()
    for row in rows:
        try:
            composition = json.loads(row["composition"] or "[]")
        except (TypeError, ValueError):
            continue
        if not isinstance(composition, list):
            continue
        referenced = {
            entry.get("ingredient_id")
            for entry in composition
            if isinstance(entry, dict)
        }
        for ingredient_id in referenced:
            if isinstance(ingredient_id, int):
                counts[ingredient_id] = counts.get(ingredient_id, 0) + 1
    return counts


def get_formula(
    conn: sqlite3.Connection, formula_id: int
) -> dict[str, Any] | None:
    """One formula by id, or None if it does not exist."""
    row = conn.execute(
        "SELECT * FROM formulas WHERE id = ?", (formula_id,)
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def _insert_version(
    conn: sqlite3.Connection,
    formula_id: int,
    version: int,
    snapshot: dict[str, Any],
    created_at: str,
) -> None:
    conn.execute(
        "INSERT INTO formula_versions (formula_id, version, snapshot, created_at)"
        " VALUES (?, ?, ?, ?)",
        (formula_id, version, json.dumps(snapshot), created_at),
    )


def create_formula(conn: sqlite3.Connection, data: dict[str, Any]) -> int:
    """Insert a formula (version 1) and its first snapshot; returns the id."""
    now = _now()
    conn.execute(
        _INSERT_SQL,
        (
            data.get("name"),
            data.get("project"),
            data.get("status") or "draft",
            data.get("family"),
            data.get("owner"),
            json.dumps(data.get("tags") or []),
            data.get("description"),
            json.dumps(data.get("custom_fields") or {}),
            json.dumps(data.get("composition") or []),
            json.dumps(data.get("params") or []),
            json.dumps(data.get("procedure") or []),
            1,
            now,
            now,
        ),
    )
    conn.commit()
    new_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    _insert_version(conn, new_id, 1, get_formula(conn, new_id), now)
    conn.commit()
    return new_id


def _composition_json(composition: Any) -> str:
    return json.dumps(composition or [], sort_keys=True)


def update_formula(
    conn: sqlite3.Connection, formula_id: int, data: dict[str, Any]
) -> bool:
    """Update a formula (partial merge with the current row).

    Returns False if the formula does not exist. The caller is responsible
    for validating the *merged* record before calling. A new version is
    created only when the composition changed (README Q2); the snapshot
    stores the full record at that moment.
    """
    current = get_formula(conn, formula_id)
    if current is None:
        return False

    merged = {**current, **data}
    merged.pop("id", None)
    merged.pop("created_at", None)
    now = _now()
    merged["updated_at"] = now

    version = current["version"]
    if _composition_json(merged.get("composition")) != _composition_json(
        current.get("composition")
    ):
        version = current["version"] + 1
        merged["version"] = version
        _insert_version(conn, formula_id, version, merged, now)
    else:
        merged["version"] = version

    conn.execute(
        _UPDATE_SQL,
        (
            merged.get("name"),
            merged.get("project"),
            merged.get("status"),
            merged.get("family"),
            merged.get("owner"),
            json.dumps(merged.get("tags") or []),
            merged.get("description"),
            json.dumps(merged.get("custom_fields") or {}),
            json.dumps(merged.get("composition") or []),
            json.dumps(merged.get("params") or []),
            json.dumps(merged.get("procedure") or []),
            merged.get("version"),
            now,
            formula_id,
        ),
    )
    conn.commit()
    return True


def delete_formula(conn: sqlite3.Connection, formula_id: int) -> bool:
    """Delete a formula and its version history; False if it did not exist."""
    conn.execute(
        "DELETE FROM formula_versions WHERE formula_id = ?", (formula_id,)
    )
    cursor = conn.execute("DELETE FROM formulas WHERE id = ?", (formula_id,))
    conn.commit()
    return cursor.rowcount > 0


def duplicate_formula(
    conn: sqlite3.Connection, source_id: int, new_name: str | None = None
) -> int | None:
    """Copy a formula into a new one (new id, version 1).

    ``new_name`` defaults to "Copy of <name>". Returns None if the source
    does not exist. Status and all content fields are copied (README §3
    "duplicate — fast start for the next iteration").
    """
    current = get_formula(conn, source_id)
    if current is None:
        return None
    name = (
        new_name.strip()
        if new_name and new_name.strip()
        else f"Copy of {current['name']}"
    )
    data = {field: current.get(field) for field in _CONTENT_FIELDS}
    data["name"] = name
    return create_formula(conn, data)


def list_formula_versions(
    conn: sqlite3.Connection, formula_id: int
) -> list[dict[str, Any]]:
    """Version history (oldest first); each row carries the full snapshot."""
    rows = conn.execute(
        "SELECT * FROM formula_versions WHERE formula_id = ? ORDER BY version",
        (formula_id,),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        data["snapshot"] = json.loads(data["snapshot"])
        result.append(data)
    return result


def get_formula_version(
    conn: sqlite3.Connection, formula_id: int, version: int
) -> dict[str, Any] | None:
    """One version row, or None if it does not exist."""
    row = conn.execute(
        "SELECT * FROM formula_versions WHERE formula_id = ? AND version = ?",
        (formula_id, version),
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["snapshot"] = json.loads(data["snapshot"])
    return data
