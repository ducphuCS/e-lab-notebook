#!/usr/bin/env python3
"""Standalone migration tool — ingredient custom fields, legacy -> current.

Archived 2026-09-07. This is the code formerly shipped as a **temporary**
in-app migration button on the Ingredients page (commit ebf9d35,
"Temporary migration — legacy custom fields", removed the same day once
every real-user database had been migrated). The tool is kept here in case
a database written before the shape change ever resurfaces; it is
intentionally self-contained (Python stdlib only) because the in-app code
it replaces no longer exists in the codebase.

Background
----------
v0 stored an ingredient's custom fields as ``name -> plain value``. Commit
9e1c865 (2026-09-07) changed the shape to ``name -> {value, unit}``, and
the service now rejects the legacy plain-value shape on **read**, so a
database that still contains legacy rows fails to load entirely. Such a
database must be rewritten in place with this tool before the app can read
it again.

Semantics (identical to the removed helpers)
--------------------------------------------
- Only rows whose custom_fields is a mapping with at least one non-dict
  entry are touched. Rows already in the current shape are untouched, so a
  second run migrates nothing (idempotent).
- Each legacy value ``v`` becomes ``{"value": ..., "unit": ""}`` — empty
  string for null, ``str(v)`` otherwise.
- Rows whose custom_fields is not valid JSON or not an object are *not*
  touched but are reported: they are corrupt, not legacy.

Usage
-----
    python archive/ingredients_custom_field_migration.py <db file>
    python archive/ingredients_custom_field_migration.py <db file> --apply

Without ``--apply`` the tool only reports the legacy rows it would rewrite
(dry run). The exit code is 0 whether or not legacy rows were found; it is
non-zero only on a real error.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


def has_legacy_entries(custom_fields: dict[str, Any]) -> bool:
    """True if any entry still uses the legacy plain-value shape.

    Current-shape entries are dicts ({value, unit}); anything else (v0
    stored plain values) is legacy and needs rewriting.
    """
    return any(not isinstance(entry, dict) for entry in custom_fields.values())


def to_new_shape(custom_fields: dict[str, Any]) -> dict[str, Any]:
    """Rewrite legacy entries to the current {value, unit} shape.

    Non-dict entries become {"value": <text>, "unit": ""}; entries already
    in the current shape pass through untouched. Idempotent.
    """
    result: dict[str, Any] = {}
    for key, entry in custom_fields.items():
        if isinstance(entry, dict):
            result[key] = entry
        else:
            result[key] = {
                "value": "" if entry is None else str(entry),
                "unit": "",
            }
    return result


def find_legacy_rows(
    conn: sqlite3.Connection,
) -> tuple[list[tuple[int, dict[str, Any]]], list[int]]:
    """(id, decoded custom_fields) legacy rows + ids of corrupt rows.

    Corrupt = the custom_fields column is not valid JSON or not an object;
    those rows are out of this migration's scope.
    """
    legacy: list[tuple[int, dict[str, Any]]] = []
    corrupt: list[int] = []
    for row in conn.execute("SELECT id, custom_fields FROM ingredients"):
        try:
            fields = json.loads(row["custom_fields"] or "{}")
        except (json.JSONDecodeError, TypeError):
            corrupt.append(int(row["id"]))
            continue
        if isinstance(fields, dict) and has_legacy_entries(fields):
            legacy.append((int(row["id"]), fields))
    return legacy, corrupt


def migrate(conn: sqlite3.Connection) -> int:
    """Rewrite legacy rows in place; returns the number updated."""
    legacy, _ = find_legacy_rows(conn)
    for row_id, fields in legacy:
        conn.execute(
            "UPDATE ingredients SET custom_fields = ? WHERE id = ?",
            (json.dumps(to_new_shape(fields)), row_id),
        )
    conn.commit()
    return len(legacy)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Rewrite legacy ingredient custom_fields "
            "({name: value}) to the current shape "
            "({name: {value, unit}}) in a SQLite database."
        )
    )
    parser.add_argument("db", type=Path, help="path to the ingredients .db file")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="perform the rewrite (default is a dry run that only reports)",
    )
    args = parser.parse_args(argv)

    if not args.db.exists():
        parser.error(f"database not found: {args.db}")

    conn = sqlite3.connect(str(args.db))
    conn.row_factory = sqlite3.Row
    try:
        legacy, corrupt = find_legacy_rows(conn)

        if corrupt:
            print(
                "Skipped corrupt custom_fields (not valid JSON or not an "
                f"object) in row ids: {', '.join(map(str, corrupt))}"
            )
        if not legacy:
            print("No legacy custom-field rows found — nothing to do.")
            return 0

        for row_id, fields in legacy:
            print(f"row {row_id}: {json.dumps(fields)}")
        print(f"{len(legacy)} legacy row(s) found.")

        if not args.apply:
            print("Dry run — rerun with --apply to rewrite them.")
            return 0

        updated = migrate(conn)
        print(f"Rewrote {updated} row(s) in place.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
