"""Formulas service — schema definitions.

Source of truth for the v0 formula schema
(frontend/formulas/README.md §5.1; Q1–Q13 resolutions).
"""

# Columns in display order; JSON columns are TEXT-encoded in SQLite.
FORMULA_FIELDS = (
    "id",
    "name",
    "project",
    "status",
    "family",
    "owner",
    "tags",
    "description",
    "custom_fields",
    "composition",
    "params",
    "procedure",
    "version",
    "created_at",
    "updated_at",
)

# Statuses offered by the UI selectbox (README Q7).
FORMULA_STATUSES = ("draft", "active", "under review", "approved", "archived")

# Aggregation methods for theoretical params (README Q3 resolution).
PARAM_AGGREGATIONS = ("sum", "avg")

FORMULAS_DDL = """
CREATE TABLE IF NOT EXISTS formulas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    project       TEXT,
    status        TEXT NOT NULL DEFAULT 'draft',
    family        TEXT,
    owner         TEXT,
    tags          TEXT NOT NULL DEFAULT '[]',
    description   TEXT,
    custom_fields TEXT NOT NULL DEFAULT '{}',
    composition   TEXT NOT NULL DEFAULT '[]',
    params        TEXT NOT NULL DEFAULT '[]',
    procedure     TEXT NOT NULL DEFAULT '[]',
    version       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT,
    updated_at    TEXT
);
"""

# Version snapshots (README Q2): a new row is appended only when the
# composition changes; the snapshot stores the full formula record at
# that moment.
FORMULA_VERSIONS_DDL = """
CREATE TABLE IF NOT EXISTS formula_versions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    formula_id INTEGER NOT NULL,
    version    INTEGER NOT NULL,
    snapshot   TEXT NOT NULL,
    created_at TEXT
);
"""
