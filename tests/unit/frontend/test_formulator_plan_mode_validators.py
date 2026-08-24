"""Unit tests for the Formulator Plan Mode page validators.

Layer: unit — frontend utilities (docs/TEST_STRATEGIES.md §4.2).
"""
import pandas as pd

from frontend.formulator_plan_mode.validators import (
    validate_formulations_df,
    validate_levels_df,
)


def _levels(**overrides) -> pd.DataFrame:
    data = {"factor": ["A", "B"], "level_1": ["1", "2"], "level_2": ["x", "y"]}
    data.update(overrides)
    return pd.DataFrame(data)


# --- validate_levels_df -------------------------------------------------

def test_valid_levels_df_passes() -> None:
    assert validate_levels_df(_levels()) == []


def test_levels_missing_column_is_reported() -> None:
    df = _levels().drop(columns=["level_2"])
    problems = validate_levels_df(df)
    assert any("level_2" in p for p in problems)


def test_levels_empty_required_cell_is_reported() -> None:
    df = _levels(factor=["A", ""])
    problems = validate_levels_df(df)
    assert any("factor" in p and "empty" in p for p in problems)


def test_levels_nan_cell_is_reported() -> None:
    df = _levels(level_1=["1", None])
    problems = validate_levels_df(df)
    assert any("level_1" in p for p in problems)


def test_levels_empty_dataframe_passes() -> None:
    df = pd.DataFrame(columns=["factor", "level_1", "level_2"])
    assert validate_levels_df(df) == []


# --- validate_formulations_df -------------------------------------------

def test_valid_formulations_passes() -> None:
    df = pd.DataFrame({"index": ["1"], "item_code": ["A-1"], "m_0": [1.0]})
    assert validate_formulations_df(df) == []


def test_formulations_negative_m0_is_reported() -> None:
    df = pd.DataFrame({"index": ["1"], "item_code": ["A-1"], "m_0": [-0.5]})
    problems = validate_formulations_df(df)
    assert any("m_0" in p for p in problems)


def test_formulations_empty_item_code_is_reported() -> None:
    df = pd.DataFrame({"index": ["1"], "item_code": [""], "m_0": [1.0]})
    problems = validate_formulations_df(df)
    assert any("item_code" in p for p in problems)


def test_formulations_missing_m0_is_reported() -> None:
    df = pd.DataFrame({"index": ["1"], "item_code": ["A-1"]})
    problems = validate_formulations_df(df)
    assert any("m_0" in p for p in problems)
