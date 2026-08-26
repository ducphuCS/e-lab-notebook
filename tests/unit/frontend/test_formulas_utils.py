"""Unit tests for the Formulas page utilities.

Layer: unit — frontend (docs/TEST_STRATEGIES.md §4.2).
"""
import pandas as pd

from frontend.formulas.utils import (
    build_formula_payload,
    composition_from_df,
    composition_to_df,
    derive_percentages,
    diff_compositions,
    formula_stats,
    ingredient_options,
    params_from_df,
    procedure_from_df,
    tags_from_text,
    tags_to_text,
)


def test_tags_roundtrip() -> None:
    assert tags_to_text(["a", "b"]) == "a, b"
    assert tags_from_text(" a,  , b ") == ["a", "b"]
    assert tags_from_text("") == []
    assert tags_from_text(None) == []


def test_ingredient_options_map() -> None:
    records = [
        {"id": 1, "name": "Water", "item_code": "W-1"},
        {"id": 2, "name": "Oil", "item_code": None},
    ]
    options, name_to_id = ingredient_options(records)
    assert options == ["Water · W-1", "Oil"]
    assert name_to_id["Water · W-1"] == 1
    assert name_to_id["Oil"] == 2


def test_composition_from_df_drops_blank_rows_and_numbers() -> None:
    df = pd.DataFrame(
        {
            "ingredient": ["Water · W-1", "", "Oil"],
            "role": ["solvent", "", "base"],
            "amount": [90.0, None, 10.0],
            "uom": ["g", "", "g"],
            "notes": [None, None, None],
        }
    )
    rows = composition_from_df(df, {"Water · W-1": 1, "Oil": 2})
    assert len(rows) == 2
    assert rows[0]["no"] == 1
    assert rows[0]["ingredient_id"] == 1
    assert rows[0]["ingredient_name"] == "Water · W-1"
    assert rows[0]["amount"] == 90.0
    assert rows[1]["no"] == 2
    assert rows[1]["amount"] == 10.0


def test_composition_from_df_empty() -> None:
    assert composition_from_df(None, {}) == []
    assert composition_from_df(pd.DataFrame(), {}) == []


def test_composition_to_df_columns() -> None:
    composition = [
        {
            "no": 1,
            "ingredient_id": 1,
            "ingredient_name": "Water",
            "role": "solvent",
            "amount": 90.0,
            "uom": "g",
            "notes": "x",
        }
    ]
    df = composition_to_df(composition)
    assert list(df.columns) == ["no", "ingredient", "role", "amount", "uom", "notes"]
    assert df.iloc[0]["ingredient"] == "Water"
    assert df.iloc[0]["amount"] == 90.0


def test_params_from_df_drops_blank_parameter() -> None:
    df = pd.DataFrame(
        {
            "parameter": ["brix", ""],
            "source": ["brix", ""],
            "aggregation": ["sum", ""],
            "value": ["10", ""],
        }
    )
    params = params_from_df(df)
    assert len(params) == 1
    assert params[0] == {
        "parameter": "brix",
        "source": "brix",
        "aggregation": "sum",
        "value": "10",
    }


def test_procedure_from_df_parses_ingredients_and_params() -> None:
    df = pd.DataFrame(
        {
            "name": ["Mix"],
            "ingredients": ["Water · W-1, Oil"],
            "equipment": ["Blender"],
            "duration": ["5 min"],
            "params": ["speed=1000; temp=70"],
        }
    )
    steps = procedure_from_df(df, {"Water · W-1": 1, "Oil": 2})
    assert len(steps) == 1
    assert steps[0]["name"] == "Mix"
    assert steps[0]["ingredients"] == [
        {"ingredient_id": 1, "ingredient_name": "Water · W-1"},
        {"ingredient_id": 2, "ingredient_name": "Oil"},
    ]
    assert steps[0]["equipment"] == "Blender"
    assert steps[0]["duration"] == "5 min"
    assert steps[0]["params"] == {"speed": "1000", "temp": "70"}


def test_procedure_from_df_drops_blank_steps() -> None:
    df = pd.DataFrame(
        {
            "name": ["", "Mix"],
            "ingredients": ["", ""],
            "equipment": ["", ""],
            "duration": ["", ""],
            "params": ["", ""],
        }
    )
    steps = procedure_from_df(df, {})
    assert len(steps) == 1
    assert steps[0]["name"] == "Mix"


def test_build_payload_blank_to_none() -> None:
    payload = build_formula_payload(
        name="  X  ",
        status="draft",
        project="",
        tags="a, b",
        description="  ",
        composition=[{"no": 1}],
    )
    assert payload["name"] == "X"
    assert payload["project"] is None
    assert payload["description"] is None
    assert payload["tags"] == ["a", "b"]
    assert payload["composition"] == [{"no": 1}]
    assert payload["params"] == []
    assert payload["procedure"] == []


def test_derive_percentages() -> None:
    composition = [
        {"no": 1, "amount": 75.0, "uom": "g"},
        {"no": 2, "amount": 25.0, "uom": "g"},
    ]
    assert derive_percentages(composition) == [75.0, 25.0]


def test_derive_percentages_none_on_mixed_uoms() -> None:
    composition = [
        {"no": 1, "amount": 75.0, "uom": "g"},
        {"no": 2, "amount": 25.0, "uom": "mL"},
    ]
    assert derive_percentages(composition) is None


def test_derive_percentages_none_on_empty_or_blank_uom() -> None:
    assert derive_percentages([]) is None
    assert derive_percentages(None) is None
    composition = [{"no": 1, "amount": 75.0, "uom": None}]
    assert derive_percentages(composition) is None


def test_formula_stats() -> None:
    record = {"composition": [1, 2], "procedure": [1, 2, 3]}
    assert formula_stats(record) == {
        "ingredients": 2,
        "steps": 3,
        "batches": 0,
        "samples": 0,
    }


def test_diff_compositions_highlights_changes() -> None:
    old = [
        {"no": 1, "ingredient_name": "Water", "amount": 90.0, "uom": "g"},
        {"no": 2, "ingredient_name": "Oil", "amount": 10.0, "uom": "g"},
    ]
    new = [{"no": 1, "ingredient_name": "Water", "amount": 95.0, "uom": "g"}]
    diff = diff_compositions(old, new)
    assert diff["changed"] == [1, 2]  # 1 edited, 2 removed
    assert len(diff["old"]) == 2
    assert len(diff["new"]) == 1
    assert diff["old"][0]["ingredient"] == "Water"
    assert diff["new"][0]["amount"] == 95.0


def test_diff_compositions_no_changes() -> None:
    old = [{"no": 1, "ingredient_name": "Water", "amount": 90.0, "uom": "g"}]
    diff = diff_compositions(old, list(old))
    assert diff["changed"] == []
