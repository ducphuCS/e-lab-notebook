"""Pure validation helpers for the DOE page.

These functions contain no ``streamlit`` imports and operate on plain
``pandas.DataFrame`` inputs, so they can be unit-tested headlessly
(docs/TEST_STRATEGIES.md §4.2). The page calls them and renders the results.

Tests: tests/unit/frontend/test_doe_validators.py
"""
from __future__ import annotations

import pandas as pd

# Required columns for each data editor on the page.
LEVELS_REQUIRED_COLUMNS = ("factor", "level_1", "level_2")
FORMULATIONS_REQUIRED_COLUMNS = ("index", "item_code", "m_0")


def validate_levels_df(df: pd.DataFrame) -> list[str]:
    """Validate the levels-of-factors editor table.

    Returns a list of human-readable problems (empty list = valid).
    """
    return _validate_required_columns(df, LEVELS_REQUIRED_COLUMNS)


def validate_formulations_df(df: pd.DataFrame) -> list[str]:
    """Validate the formulations draft editor table.

    Returns a list of human-readable problems (empty list = valid).
    """
    problems = _validate_required_columns(df, FORMULATIONS_REQUIRED_COLUMNS)
    if "m_0" in df.columns and pd.to_numeric(df["m_0"], errors="coerce").lt(0).any():
        problems.append("m_0 must not be negative.")
    return problems


def _validate_required_columns(df: pd.DataFrame, required: tuple[str, ...]) -> list[str]:
    """Check that required columns exist and contain no empty cells."""
    problems: list[str] = []
    missing = [col for col in required if col not in df.columns]
    if missing:
        problems.append(f"Missing required columns: {', '.join(missing)}.")
    for col in required:
        if col in df.columns and (
            df[col].isna() | df[col].astype(str).str.strip().eq("")
        ).any():
            problems.append(f"Column '{col}' has empty required cells.")
    return problems
