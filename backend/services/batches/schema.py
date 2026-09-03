"""Batches service — schema definitions.

Source of truth for the v0 batch schema
(frontend/batches/README.md §5.1; Q1–Q8 resolutions).
"""

# Columns in display order; JSON columns are TEXT-encoded in SQLite.
BATCH_FIELDS = (
    "id",
    "batch_code",
    "name",
    "formula_id",
    "formula_name",
    "formula_version",
    "planned",
    "actual",
    "status",
    "owner",
    "created_at",
    "updated_at",
)

# Statuses offered by the UI selectbox (README Q5): the batch starts as a
# plan, then records the run as it happens.
BATCH_STATUSES = ("planned", "in progress", "completed")

# Fields pinned at creation and immutable afterwards (README Q1: a batch is
# frozen history — id for links, batch_code for identity, formula reference
# + name + version say what the batch was made from). The gateway refuses
# updates that try to change them. 'planned' is NOT here: it is editable,
# but only while the batch is still 'planned' (decision log 2026-09-03).
IMMUTABLE_FIELDS = (
    "id",
    "batch_code",
    "formula_id",
    "formula_name",
    "formula_version",
    "created_at",
)

BATCHES_DDL = """
CREATE TABLE IF NOT EXISTS batches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_code      TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    formula_id      INTEGER NOT NULL,
    formula_name    TEXT NOT NULL,
    formula_version INTEGER NOT NULL,
    planned         TEXT NOT NULL DEFAULT '{}',
    actual          TEXT NOT NULL DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'planned',
    owner           TEXT,
    created_at      TEXT,
    updated_at      TEXT
);
"""

# Single-row counter for batch_code generation (README Q4): monotonic, so
# codes are never reused even when a 'planned' batch is deleted. Kept out
# of the batches table so deletion of rows never affects the sequence.
BATCH_SEQ_DDL = """
CREATE TABLE IF NOT EXISTS batch_seq (
    id       INTEGER PRIMARY KEY CHECK (id = 1),
    next_val INTEGER NOT NULL
);
"""
