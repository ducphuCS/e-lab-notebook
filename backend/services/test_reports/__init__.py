"""backend.services.test_reports — SQLite-backed test-report service (v0).

Implements the schema and persistence decisions from
frontend/test_reports/README.md (§5). stdlib only (sqlite3) — no
streamlit, no pandas: the store stays headless-testable per
docs/TEST_STRATEGIES.md §4.1.
"""
