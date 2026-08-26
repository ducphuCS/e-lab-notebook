"""backend.services.formulas — SQLite-backed formula service (v0).

Implements the schema and persistence decisions from
frontend/formulas/README.md (§5). stdlib only (sqlite3, json) — no
streamlit, no pandas: the store stays headless-testable per
docs/TEST_STRATEGIES.md §4.1.
"""
