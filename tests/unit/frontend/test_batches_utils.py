"""Unit tests for the pure Batches page helpers.

Layer: unit — frontend (docs/TEST_STRATEGIES.md §4.2). Pure functions,
no streamlit runtime: scaling + same-unit guard, the planned snapshot,
deviation, and the DataFrame <-> stored-rows conversions.
"""
import pandas as pd

from frontend.batches import utils


def _formula(**overrides) -> dict:
    data = {
        "id": 5,
        "name": "Emulsion X",
        "version": 3,
        "composition": [
            {
                "no": 1,
                "ingredient_id": 7,
                "ingredient_name": "Water",
                "role": "solvent",
                "amount": 90.0,
                "uom": "g",
                "notes": None,
            },
            {
                "no": 2,
                "ingredient_id": 8,
                "ingredient_name": "Oil",
                "role": "emollient",
                "amount": 10.0,
                "uom": "g",
                "notes": None,
            },
        ],
        "procedure": [
            {
                "name": "Mix",
                "ingredients": [],
                "equipment": "Blender",
                "duration": "5 min",
                "params": [{"name": "speed", "value": "1000", "unit": "rpm"}],
            }
        ],
    }
    data.update(overrides)
    return data


def _record(**overrides) -> dict:
    data = {
        "id": 1,
        "batch_code": "B-0001",
        "name": "Emulsion 2500g",
        "formula_id": 5,
        "formula_name": "Emulsion X",
        "formula_version": 3,
        "planned": utils.build_planned(_formula(), target_amount=2500.0, target_uom="g"),
        "actual": {
            "composition": [],
            "yield": {"amount": 2480.0, "uom": "g"},
            "observations": "Fine.",
        },
        "status": "in progress",
        "owner": None,
        "created_at": "2026-09-03T10:00:00+00:00",
        "updated_at": "2026-09-03T10:00:00+00:00",
    }
    data.update(overrides)
    return data


# --- formula options -------------------------------------------------------

def test_formula_options_labels_and_map() -> None:
    options, label_to_id = utils.formula_options(
        [_formula(id=1, name="A"), _formula(id=2, name="B")]
    )
    assert options == ["A", "B"]
    assert label_to_id == {"A": 1, "B": 2}


def test_formula_options_disambiguates_duplicate_names() -> None:
    options, label_to_id = utils.formula_options(
        [_formula(id=1, name="A"), _formula(id=2, name="A")]
    )
    assert "A (id 1)" in options and "A (id 2)" in options
    assert label_to_id["A (id 1)"] == 1
    assert label_to_id["A (id 2)"] == 2


# --- planned snapshot & scaling (README Q3) --------------------------------

def test_normalize_plan_rows_renumbers_and_strips_role() -> None:
    rows = utils.normalize_plan_rows(
        [
            {"no": 3, "ingredient_id": 7, "ingredient_name": "Water",
             "role": "solvent", "amount": 90.0, "uom": "g"},
            {"no": 1, "ingredient_id": "", "ingredient_name": "", "amount": 1.0},
        ]
    )
    assert rows == [
        {"no": 1, "ingredient_id": 7, "ingredient_name": "Water",
         "amount": 90.0, "uom": "g", "notes": None}
    ]
    assert all("role" not in row for row in rows)


def test_scale_guard_reason_none_when_scalable() -> None:
    formula = _formula()
    rows = utils.normalize_plan_rows(formula["composition"])
    assert utils.scale_guard_reason(rows) is None


def test_scale_guard_reason_mixed_units() -> None:
    formula = _formula(
        composition=[
            {"no": 1, "ingredient_id": 7, "ingredient_name": "Water",
             "amount": 90.0, "uom": "g", "notes": None},
            {"no": 2, "ingredient_id": 8, "ingredient_name": "Fragrance",
             "amount": 1.0, "uom": "drops", "notes": None},
        ]
    )
    rows = utils.normalize_plan_rows(formula["composition"])
    assert utils.scale_guard_reason(rows) is not None


def test_scale_guard_reason_missing_amounts_or_uom() -> None:
    rows = utils.normalize_plan_rows(
        [{"no": 1, "ingredient_id": 7, "ingredient_name": "Water",
          "amount": None, "uom": "g", "notes": None}]
    )
    assert utils.scale_guard_reason(rows) is not None
    rows = utils.normalize_plan_rows(
        [{"no": 1, "ingredient_id": 7, "ingredient_name": "Water",
          "amount": 1.0, "uom": "", "notes": None}]
    )
    assert utils.scale_guard_reason(rows) is not None


def test_build_planned_scales_to_target() -> None:
    planned = utils.build_planned(_formula(), target_amount=2500.0, target_uom="g")
    assert planned["target_yield"] == {"amount": 2500.0, "uom": "g"}
    # 90/100 * 2500 = 2250; 10/100 * 2500 = 250
    amounts = [row["amount"] for row in planned["composition"]]
    assert amounts == [2250.0, 250.0]
    # processing snapshot copied from the formula
    assert planned["processing"][0]["name"] == "Mix"


def test_build_planned_without_target_copies_rows() -> None:
    planned = utils.build_planned(_formula())
    assert "target_yield" not in planned
    assert [row["amount"] for row in planned["composition"]] == [90.0, 10.0]


def test_build_planned_mixed_units_falls_back_unscaled() -> None:
    formula = _formula(
        composition=[
            {"no": 1, "ingredient_id": 7, "ingredient_name": "Water",
             "amount": 90.0, "uom": "g", "notes": None},
            {"no": 2, "ingredient_id": 8, "ingredient_name": "Fragrance",
             "amount": 1.0, "uom": "drops", "notes": None},
        ]
    )
    planned = utils.build_planned(formula, target_amount=1000.0, target_uom="g")
    # unscalable -> rows as-is, no target stored
    assert "target_yield" not in planned
    assert [row["amount"] for row in planned["composition"]] == [90.0, 1.0]


def test_build_planned_empty_composition_returns_none() -> None:
    assert utils.build_planned(_formula(composition=[])) is None


# --- getters / deviation ---------------------------------------------------

def test_yield_text() -> None:
    assert utils.yield_text({"amount": 2480.0, "uom": "g"}) == "2480 g"
    assert utils.yield_text(None) == "—"
    assert utils.yield_text({}) == "—"


def test_deviation_only_when_units_match() -> None:
    assert utils.deviation(2250.0, "g", 2240.0, "g") == -10.0
    assert utils.deviation(2250.0, "g", 2240.0, "kg") is None
    assert utils.deviation(2250.0, "g", None, "g") is None
    assert utils.deviation(None, "g", 2240.0, "g") is None


def test_batch_stats_placeholders() -> None:
    assert utils.batch_stats(_record()) == {"samples": 0, "reports": 0}


# --- composition editor ----------------------------------------------------

def test_composition_editor_df_merges_plan_and_actual() -> None:
    record = _record(
        actual={
            "composition": [
                {
                    "no": 1,
                    "ingredient_id": 7,
                    "ingredient_name": "Water",
                    "amount": 2240.0,
                    "uom": "g",
                    "note": "slightly under",
                }
            ],
            "yield": None,
            "observations": "",
        }
    )
    df = utils.composition_editor_df(record)
    # visible columns first, hidden identity columns appended after them
    assert list(df.columns) == list(utils.COMPOSITION_EDITOR_COLUMNS) + list(
        utils.COMPOSITION_EDITOR_HIDDEN_COLUMNS
    )
    assert len(df) == 2
    row1 = df.iloc[0]
    assert row1["no"] == 1
    assert row1["ingredient"] == "Water"
    assert row1["ingredient_id"] == 7
    assert row1["ingredient_name"] == "Water"
    assert row1["planned"] == 2250.0
    assert row1["actual"] == 2240.0
    assert row1["deviation"] == -10.0
    assert row1["actual_uom"] == "g"
    # untouched second row: no actual, uom prefilled from the plan
    row2 = df.iloc[1]
    assert pd.isna(row2["actual"])
    assert pd.isna(row2["deviation"])
    assert row2["actual_uom"] == "g"


def test_actual_from_editor_keeps_only_recorded_rows() -> None:
    df = pd.DataFrame(
        [
            {"no": 1, "ingredient_id": 7, "ingredient_name": "Water",
             "actual": 2240.0, "actual_uom": "g", "note": "ok"},
            {"no": 2, "ingredient_id": 8, "ingredient_name": "Oil",
             "actual": None, "actual_uom": "g", "note": ""},
            {"no": 3, "ingredient_id": 9, "ingredient_name": "Gum",
             "actual": None, "actual_uom": "g", "note": "added last"},
        ]
    )
    rows = utils.actual_from_editor(df)
    assert [r["no"] for r in rows] == [1, 3]
    assert rows[0]["amount"] == 2240.0
    assert rows[0]["ingredient_id"] == 7
    assert rows[1]["note"] == "added last"
    assert rows[1]["amount"] is None
    assert rows[1]["ingredient_id"] == 9


def test_editor_to_actual_roundtrip_keeps_int_ids_and_validates() -> None:
    """Regression: saving actual amounts used to fail with 'Cannot
    update batch' because the editor dropped its hidden identity columns
    (COMPOSITION_EDITOR_COLUMNS omitted them from the DataFrame), so
    actual_from_editor emitted ingredient_id=None and backend validation
    rejected the row. The hidden columns must ride along in the editor
    data, and the rebuilt rows must pass backend validation."""
    from backend.services.batches.validation import validate_batch

    record = _record()  # planned rows: Water (id 7), Oil (id 8)
    editor = utils.composition_editor_df(record)
    # simulate the user typing an actual amount into the first row
    editor.loc[0, "actual"] = 2240.0
    rows = utils.actual_from_editor(editor)
    assert rows, "a recorded row was expected"
    assert rows[0]["no"] == 1
    assert rows[0]["ingredient_id"] == 7
    assert rows[0]["ingredient_name"] == "Water"
    assert rows[0]["amount"] == 2240.0
    # the stored actual must satisfy the backend's type-only validation
    payload = {"actual": {"composition": rows}}
    assert validate_batch(dict(record, **payload)) == []


# --- plan editor (edit-while-planned) --------------------------------------

def test_plan_editor_roundtrip_keeps_identity() -> None:
    record = _record()
    df = utils.plan_editor_df(record)
    assert len(df) == 2
    # user tweaks amounts/uoms/notes
    df.loc[0, "amount"] = 2300.0
    df.loc[0, "notes"] = "bumped up"
    rows = utils.plan_from_editor_df(df, utils.planned_rows(record))
    assert rows[0]["no"] == 1
    assert rows[0]["ingredient_id"] == 7
    assert rows[0]["ingredient_name"] == "Water"
    assert rows[0]["amount"] == 2300.0
    assert rows[0]["notes"] == "bumped up"
    assert rows[1]["amount"] == 250.0


def test_plan_editor_drops_rows_that_disappear_from_editor() -> None:
    record = _record()
    df = utils.plan_editor_df(record)
    df = df.iloc[:1]  # editor lost the second row
    rows = utils.plan_from_editor_df(df, utils.planned_rows(record))
    assert len(rows) == 1


# --- processing snapshot (Q8) ---------------------------------------------

def test_processing_df_flattens_steps_and_params() -> None:
    formula = _formula(
        procedure=[
            {
                "name": "Mix",
                "ingredients": [],
                "equipment": "Blender",
                "duration": "5 min",
                "params": [
                    {"name": "speed", "value": "1000", "unit": "rpm"},
                    {"name": "temp", "value": "40", "unit": "C"},
                ],
            },
            {"name": "Cool", "ingredients": [], "equipment": None,
             "duration": None, "params": []},
        ]
    )
    record = _record(planned=utils.build_planned(formula, target_amount=2500.0, target_uom="g"))
    df = utils.processing_df(record)
    assert len(df) == 3
    assert df.iloc[0]["step"] == "1. Mix"
    assert df.iloc[0]["parameter"] == "speed"
    assert df.iloc[2]["step"] == "2. Cool"
    assert pd.isna(df.iloc[2]["parameter"])
