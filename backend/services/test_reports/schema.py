"""Test Reports service — schema definitions.

Source of truth for the v0 test-report schema
(frontend/test_reports/README.md §5.1, Q1–Q16 resolutions).
"""

# Columns in display order.
REPORT_FIELDS = (
    "id",
    "test_method",
    "evaluation_date",
    "person_in_charge",
    "methodology",
    "equipment",
    "panel",
    "notes",
    "created_at",
    "updated_at",
)

RESULT_FIELDS = (
    "id",
    "report_id",
    "sample_id",
    "transfer_id",
    "parameter",
    "value",
    "unit",
    "notes",
    "created_at",
    "updated_at",
)

# v0 uses a single generic template (README Q3/Q4): `test_method` is a
# free-text label that later becomes a `test_method_id` FK to the Test
# Methods master. No report-family enum is enforced here.

TEST_REPORTS_DDL = """
CREATE TABLE IF NOT EXISTS test_reports (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    test_method      TEXT NOT NULL,
    evaluation_date  TEXT NOT NULL,
    person_in_charge TEXT,
    methodology      TEXT,
    equipment        TEXT,
    panel            TEXT,
    notes            TEXT,
    created_at       TEXT,
    updated_at       TEXT
);
"""

TEST_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS test_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id   INTEGER NOT NULL,
    sample_id   INTEGER NOT NULL,
    transfer_id INTEGER NOT NULL,
    parameter   TEXT NOT NULL,
    value       REAL NOT NULL,
    unit        TEXT,
    notes       TEXT,
    created_at  TEXT,
    updated_at  TEXT
);
"""
