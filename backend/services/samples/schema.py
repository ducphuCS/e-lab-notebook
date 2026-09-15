"""Samples service — schema definitions.

Source of truth for the v0 sample schema
(frontend/samples/README.md §5.1; Q1–Q15 resolutions).
"""

# Columns in display order.
SAMPLE_FIELDS = (
    "id",
    "sample_code",
    "origin",
    "batch_id",
    "source",
    "taken_at",
    "status",
    "notes",
    "created_at",
    "updated_at",
)

TRANSFER_FIELDS = (
    "id",
    "sample_id",
    "kind",
    "to_team",
    "sent_at",
    "storage_condition",
    "sent_by",
    "notes",
)

# Statuses offered by the UI selectbox (README Q4): user-set, default active.
SAMPLE_STATUSES = ("active", "depleted", "expired")

# Where a sample comes from (README Q1/Q14): batch-born requires a batch,
# benchmark is standalone (e.g. a market product).
SAMPLE_ORIGINS = ("batch", "benchmark")

# Handoff kinds (README Q6/Q7): exactly one `retention` row per sample
# anchors test reports; `dispatch` records a handoff to another team.
TRANSFER_KINDS = ("retention", "dispatch")

# One general storage-condition list for all teams, hardcoded in v0
# (README Q15).
STORAGE_CONDITIONS = ("refrigerator", "room temperature", "TA35", "TA45")

# Sample identity (README Q3/Q11): a unique 3-character code. Ambiguous
# characters are excluded: I, L, O and the digits 0, 1.
SAMPLE_CODE_LENGTH = 3
SAMPLE_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

# Fields pinned at creation and immutable afterwards (README Q3/Q11/Q14 —
# provenance is frozen: the code is the sample's identity, origin/batch_id
# say where it came from). The gateway refuses updates that change them.
IMMUTABLE_FIELDS = (
    "id",
    "sample_code",
    "origin",
    "batch_id",
    "created_at",
)

# Sample transfers (README Q6/Q7) carry no created_at/updated_at in v0 —
# the letter's schema lists only the event fields.
SAMPLES_DDL = """
CREATE TABLE IF NOT EXISTS samples (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_code TEXT NOT NULL UNIQUE,
    origin      TEXT NOT NULL DEFAULT 'batch',
    batch_id    INTEGER,
    source      TEXT,
    taken_at    TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    notes       TEXT,
    created_at  TEXT,
    updated_at  TEXT
);
"""

SAMPLE_TRANSFERS_DDL = """
CREATE TABLE IF NOT EXISTS sample_transfers (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_id         INTEGER NOT NULL,
    kind              TEXT NOT NULL DEFAULT 'dispatch',
    to_team           TEXT,
    sent_at           TEXT,
    storage_condition TEXT,
    sent_by           TEXT,
    notes             TEXT
);
"""
