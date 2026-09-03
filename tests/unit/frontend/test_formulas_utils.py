"""Unit tests for the Formulas page utilities.

Layer: unit — frontend (docs/TEST_STRATEGIES.md §4.2).
"""
import pandas as pd

from frontend.formulas.utils import (
    build_formula_payload,
    composition_from_df,
    composition_step_options,
    composition_to_df,
    delete_block_reason,
    derive_percentages,
    diff_compositions,
    formula_stats,
    ingredient_options,
    linear_flow_digraph,
    params_from_df,
    step_params_from_df,
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


def test_composition_step_options_unique() -> None:
    composition = [
        {"ingredient_id": 1, "ingredient_name": "Water · W-1"},
        {"ingredient_id": 2, "ingredient_name": "Oil"},
        {"ingredient_id": 1, "ingredient_name": "Water · W-1"},
    ]
    options, name_to_id = composition_step_options(composition)
    assert options == ["Water · W-1", "Oil"]
    assert name_to_id == {"Water · W-1": 1, "Oil": 2}
    assert composition_step_options(None) == ([], {})


def test_step_params_from_df_parses_name_value_unit() -> None:
    df = pd.DataFrame(
        {
            "name": ["speed", "temp", ""],
            "value": ["1000", "70", "9"],
            "unit": ["rpm", "°C", "x"],
        }
    )
    params = step_params_from_df(df)
    assert params == [
        {"name": "speed", "value": "1000", "unit": "rpm"},
        {"name": "temp", "value": "70", "unit": "°C"},
    ]


def test_step_params_from_df_drops_blank_rows() -> None:
    assert step_params_from_df(None) == []
    blank = pd.DataFrame(
        {"name": [""], "value": [""], "unit": [""]}
    )
    assert step_params_from_df(blank) == []


def test_linear_flow_digraph_renders_linear_graph() -> None:
    steps = [{"name": "Mix"}, {"name": "Heat"}, {"name": "Cool"}]
    digraph = linear_flow_digraph(steps, selected=1)
    source = digraph.source
    assert "rankdir=TB" in source  # top-to-bottom flow
    assert "step_1 -> step_2" in source
    assert "step_2 -> step_3" in source
    assert "Mix" in source and "Heat" in source and "Cool" in source
    # the selected step is highlighted, the others are not
    assert 'fillcolor="#e8f0fe"' in source
    assert 'fillcolor="#f7f7f8"' in source


def test_linear_flow_digraph_single_step_has_no_edges() -> None:
    digraph = linear_flow_digraph([{"name": "Mix"}])
    source = digraph.source
    assert "->" not in source
    assert "Mix" in source


def test_linear_flow_digraph_empty() -> None:
    assert "digraph" in linear_flow_digraph([]).source


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


# --- delete guard (README Q12, decision log 2026-09-03) --------------------

def test_delete_block_reason_none_when_no_batches() -> None:
    assert delete_block_reason(None) is None
    assert delete_block_reason([]) is None


def test_delete_block_reason_lists_related_batches() -> None:
    batches = [
        {"id": 1, "batch_code": "B-0001", "name": "Run", "status": "planned"},
        {"id": 2, "batch_code": "B-0002", "name": "Run 2", "status": "planned"},
    ]
    reason = delete_block_reason(batches)
    assert reason is not None
    assert "2 batches" in reason
    assert "B-0001" in reason and "B-0002" in reason


def test_delete_block_reason_falls_back_to_id_without_code() -> None:
    reason = delete_block_reason([{"id": 7, "name": "Run"}])
    assert reason is not None
    assert "#7" in reason
