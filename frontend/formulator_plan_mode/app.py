import pandas as pd
import streamlit as st

# The project is installed editable (uv sync), so the repo root is on
# sys.path and root-relative imports work in every launch mode.
from frontend.formulator_plan_mode.validators import (
    validate_formulations_df,
    validate_levels_df,
)

st.set_page_config(page_title="Formulator Plan Mode", layout="wide")

st.title("Formulator Plan Mode")

st.header("1. Record Intent & Notes")
intent_notes = st.text_area("Record your intent and notes during the experiment here:", height=100, help="Log your thoughts, rationales, and observations.")

st.divider()

# Toggle for experiment details
show_experiment = st.toggle("Show Experiment Details", value=True)

# Determine the layout based on the toggle
if show_experiment:
    col_exp, col_form = st.columns([1, 1], gap="large")
    with col_exp:
        st.header("Experiment Details")
        st.write("Draft your experiment parameters and context here.")
        context = st.text_area("Context (Optional)", help="Enter any background context for this experiment.")
        objectives = st.text_area("Objectives", help="What are the main objectives of this experiment?")
        hypothesis = st.text_area("Hypothesis", help="What is your hypothesis?")
        
        fixed_factors = st.text_area("Fixed Factors", help="List the fixed factors being tested.")
        
        st.write("Levels of Factors")
        if 'levels_df' not in st.session_state:
            st.session_state.levels_df = pd.DataFrame(columns=["factor", "level_1", "level_2"])
                
        levels_df = st.data_editor(
            st.session_state.levels_df,
            num_rows="dynamic",
            width="stretch",
            column_config={
                "factor": st.column_config.TextColumn("Factor", required=True),
                "level_1": st.column_config.TextColumn("Level 1", required=True),
                "level_2": st.column_config.TextColumn("Level 2", required=True)
            },
            key="levels_editor"
        )
        levels_problems = validate_levels_df(levels_df)
        
        outcomes = st.text_area("Outcomes", help="Expected or observed outcomes.")
    
    # Place the formulations in the right column
    form_container = col_form
else:
    # If hidden, the form container takes the full width of the page
    form_container = st.container()
    levels_problems: list[str] = []

with form_container:
    st.header("2. Formulations Draft")
    st.write("Draft your formulations below.")

    # Initialize the formulation dataframe in session state if it doesn't exist
    if 'formulations_df' not in st.session_state:
        st.session_state.formulations_df = pd.DataFrame(columns=["index", "item_code", "item_description", "uom", "m_0"])

    # Display data editor
    edited_df = st.data_editor(
        st.session_state.formulations_df,
        num_rows="dynamic",
        width="stretch",
        height="content",
        column_config={
            "index": st.column_config.TextColumn("Index", required=True),
            "item_code": st.column_config.TextColumn("Item Code", required=True),
            "item_description": st.column_config.TextColumn("Item Description"),
            "uom": st.column_config.TextColumn("UOM"),
            "m_0": st.column_config.NumberColumn("M0", required=True, min_value=0.0, format="%.4f")
        },
        key="formulation_editor"
    )

formulations_problems = validate_formulations_df(edited_df)
problems = levels_problems + formulations_problems

st.divider()
if st.button("Save Experiment & Draft", type="primary"):
    if problems:
        st.error("Cannot save — please fix the following:\n\n- " + "\n- ".join(problems))
    else:
        st.success("Experiment drafted successfully!")
