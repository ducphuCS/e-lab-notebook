"""Shared dialogs for the Formulas pages (overview and detail).

st.dialog modals per README Q4/Q13 — one implementation, launched from
both entry points. Pages stay thin glue (docs/TEST_STRATEGIES.md §5):
the dialogs call the gateway directly and reuse the pure helpers in
utils.py.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from backend.gateway import formulas as gw
from backend.gateway import ingredients as igw
from backend.services.formulas.schema import FORMULA_STATUSES, PARAM_AGGREGATIONS
from backend.services.ingredients.store import DEV_DB_PATH as INGREDIENTS_DB_PATH

from frontend.formulas.utils import (
    FORMULAS_TABLE_KEY,
    build_formula_payload,
    composition_from_df,
    composition_to_df,
    custom_fields_from_df,
    custom_fields_to_df,
    ingredient_options,
    params_from_df,
    params_to_df,
    procedure_from_df,
    procedure_to_df,
    tags_to_text,
)


def _load_ingredients() -> list[dict]:
    """Ingredient master records for the composition/procedure editors."""
    if "formulas_ingredients_conn" not in st.session_state:
        st.session_state.formulas_ingredients_conn = igw.connect(
            INGREDIENTS_DB_PATH
        )
    conn = st.session_state.formulas_ingredients_conn
    try:
        return igw.list_ingredients(conn)
    except igw.GatewayError as exc:
        st.error(f"Could not load ingredients: {exc}")
        return []


@st.dialog("Formula")
def form_dialog(conn: Any, record: dict | None) -> None:
    """Create (record=None) or edit (record=dict) dialog (README Q4/Q13)."""
    is_edit = record is not None
    record = record or {}
    record_id = record.get("id", "new")

    ingredients = _load_ingredients()
    options, name_to_id = ingredient_options(ingredients)

    st.markdown(f"### {'Edit formula' if is_edit else 'New formula'}")
    with st.form(f"formula_form_{record_id}"):
        name = st.text_input(
            "Name *",
            value=record.get("name", ""),
            placeholder="Formula name",
        )
        c1, c2 = st.columns(2)
        status_index = 0
        if record.get("status") in FORMULA_STATUSES:
            status_index = FORMULA_STATUSES.index(record["status"])
        status = c1.selectbox(
            "Status", FORMULA_STATUSES, index=status_index
        )
        project = c2.text_input("Project", value=record.get("project") or "")
        family = st.text_input("Family", value=record.get("family") or "")
        owner = st.text_input("Owner", value=record.get("owner") or "")
        tags = st.text_input(
            "Tags", value=tags_to_text(record.get("tags")), help="Comma-separated"
        )
        description = st.text_area(
            "Description", value=record.get("description") or ""
        )

        st.write("**Composition**")
        if not options:
            st.caption(
                "No ingredients yet — add them on the Ingredients page first."
            )
        composition_editor = st.data_editor(
            composition_to_df(record.get("composition")),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            column_config={
                "ingredient": st.column_config.SelectboxColumn(
                    "Ingredient", options=options
                ),
                "role": st.column_config.TextColumn("Role"),
                "amount": st.column_config.NumberColumn(
                    "Amount", min_value=0.0
                ),
                "uom": st.column_config.TextColumn("UOM"),
                "notes": st.column_config.TextColumn("Notes"),
            },
            key=f"composition_{record_id}",
        )

        st.write("**Params**")
        st.caption(
            "Theoretical params — source is an ingredient custom field, "
            "aggregation says how values combine (evaluation is a later phase)."
        )
        params_editor = st.data_editor(
            params_to_df(record.get("params")),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            column_config={
                "parameter": st.column_config.TextColumn("Parameter", required=True),
                "source": st.column_config.TextColumn("Source custom field"),
                "aggregation": st.column_config.SelectboxColumn(
                    "Aggregation", options=list(PARAM_AGGREGATIONS)
                ),
                "value": st.column_config.TextColumn("Value"),
            },
            key=f"params_{record_id}",
        )

        st.write("**Procedure**")
        st.caption(
            "Ingredients: comma-separated names from the master. "
            "Params: key=value pairs separated by ';'."
        )
        procedure_editor = st.data_editor(
            procedure_to_df(record.get("procedure")),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            column_config={
                "name": st.column_config.TextColumn("Step name", required=True),
                "ingredients": st.column_config.TextColumn("Ingredients"),
                "equipment": st.column_config.TextColumn("Equipment"),
                "duration": st.column_config.TextColumn("Duration"),
                "params": st.column_config.TextColumn("Processing params"),
            },
            key=f"procedure_{record_id}",
        )

        st.write("**Custom fields**")
        custom_editor = st.data_editor(
            custom_fields_to_df(record.get("custom_fields")),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            column_config={
                "key": st.column_config.TextColumn("Key"),
                "value": st.column_config.TextColumn("Value"),
            },
            key=f"custom_{record_id}",
        )
        submitted = st.form_submit_button("Save", type="primary")

    if st.button("Cancel", key=f"cancel_form_{record_id}"):
        st.rerun()

    if submitted:
        payload = build_formula_payload(
            name=name,
            status=status,
            project=project,
            family=family,
            owner=owner,
            tags=tags,
            description=description,
            custom_fields=custom_fields_from_df(custom_editor),
            composition=composition_from_df(composition_editor, name_to_id),
            params=params_from_df(params_editor),
            procedure=procedure_from_df(procedure_editor, name_to_id),
        )
        try:
            # st.toast survives the rerun below (st.success would not).
            if is_edit:
                gw.update_formula(conn, record["id"], payload)
                st.toast("Formula updated.")
            else:
                gw.create_formula(conn, payload)
                st.toast("Formula created.")
        except gw.GatewayError as exc:
            problems = exc.problems or [str(exc)]
            st.error("Could not save formula:\n- " + "\n- ".join(problems))
        else:
            st.rerun()


@st.dialog("Delete formula")
def delete_dialog(conn: Any, record: dict) -> None:
    """Delete confirmation (README Q12 — blocked once links exist)."""
    st.warning(
        f"Delete **{record['name']}** (ID {record['id']})? This cannot be "
        "undone. Deletion is blocked once the formula has linked batches "
        "or samples — none yet, so this is safe."
    )
    c1, c2 = st.columns(2)
    if c1.button("Confirm delete", type="primary"):
        try:
            gw.delete_formula(conn, record["id"])
        except gw.GatewayError as exc:
            st.error(f"Delete failed: {exc}")
        else:
            st.toast("Formula deleted.")
            # The deleted row was selected; drop the stale selection so the
            # overview table does not keep an out-of-bounds index on rerun.
            if FORMULAS_TABLE_KEY in st.session_state:
                st.session_state[FORMULAS_TABLE_KEY] = {
                    "selection": {"rows": []}
                }
            st.rerun()
    if c2.button("Cancel", key="cancel_delete"):
        st.rerun()


@st.dialog("Duplicate formula")
def duplicate_dialog(conn: Any, record: dict) -> None:
    """Duplicate into a new formula (README §3 — fast start)."""
    st.markdown(
        f"Duplicate **{record['name']}** (ID {record['id']}) into a new "
        "formula. Status and all content are copied; the copy starts at "
        "version 1."
    )
    new_name = st.text_input("New name", value=f"Copy of {record['name']}")
    c1, c2 = st.columns(2)
    if c1.button("Duplicate", type="primary"):
        try:
            new_record = gw.duplicate_formula(conn, record["id"], new_name)
        except gw.GatewayError as exc:
            st.error(f"Duplicate failed: {exc}")
        else:
            st.toast(f"Formula duplicated as '{new_record['name']}'.")
            st.rerun()
    if c2.button("Cancel", key="cancel_duplicate"):
        st.rerun()
