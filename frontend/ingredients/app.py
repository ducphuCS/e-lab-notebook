"""Ingredients page (Library section).

Two-column layout (frontend/ingredients/README.md §4):
- left: read-only list of all ingredients with single-row selection
- right: details of the selected ingredient, or an explicit create/edit
  form and delete flow (README §7, Q3 resolution)

The page stays thin glue (docs/TEST_STRATEGIES.md §5): widgets -> gateway
call -> display. Pure helpers live in utils.py; service + gateway live in
backend/.
"""
import pandas as pd
import streamlit as st

from backend.gateway import ingredients as gw
from backend.services.ingredients.schema import INGREDIENT_STATES
from backend.services.ingredients.store import DEV_DB_PATH

from frontend.ingredients.utils import (
    build_ingredient_payload,
    custom_fields_from_df,
    custom_fields_to_df,
)
from frontend.common import configure_page

configure_page()

# Header row: page title left, primary "Add" button top-right.
title_col, add_col = st.columns([5, 1], vertical_alignment="center")
with title_col:
    st.title("Ingredients")
with add_col:
    if st.button(
        "➕ Add ingredient",
        type="primary",
        use_container_width=True,
        key="add_ingredient",
    ):
        st.session_state.ingredients_mode = "create"
        st.session_state.ingredients_confirm_delete_id = None
        st.rerun()

# Smaller metric values in the Details panel (owner request).
st.html(
    """
    <style>
    [data-testid="stMetricValue"] { font-size: 1.1rem; }
    </style>
    """
)


# ------------------------------------------------------------------ data
if "ingredients_conn" not in st.session_state:
    st.session_state.ingredients_conn = gw.connect(DEV_DB_PATH)
conn = st.session_state.ingredients_conn

try:
    records = gw.list_ingredients(conn)
except gw.GatewayError as exc:
    st.error(f"Could not load ingredients: {exc}")
    records = []

df = pd.DataFrame(records)

# ------------------------------------------------------------------ state
if "ingredients_mode" not in st.session_state:
    st.session_state.ingredients_mode = None  # None | "create" | record id
if "ingredients_selected_id" not in st.session_state:
    st.session_state.ingredients_selected_id = None
if "ingredients_confirm_delete_id" not in st.session_state:
    st.session_state.ingredients_confirm_delete_id = None


def _reset_to_details() -> None:
    st.session_state.ingredients_mode = None
    st.session_state.ingredients_confirm_delete_id = None


# ------------------------------------------------------------ right panel
def _render_details(conn, selected_id: int | None) -> None:
    if selected_id is None:
        st.info("Select an ingredient on the left to see its details.")
        return

    record = gw.get_ingredient(conn, selected_id)
    if record is None:
        st.warning("The selected ingredient no longer exists.")
        return

    st.markdown(f"### {record['name']}")
    st.caption(f"ID {record['id']}")

    g1a, g1b = st.columns(2)
    g1a.metric("Item code", record["item_code"] or "—")
    g1b.metric("Item description", record["item_description"] or "—")

    g2a, g2b, g2c = st.columns(3)
    g2a.metric("Supplier", record["supplier"] or "—")
    g2b.metric("UOM", record["uom"] or "—")
    g2c.metric("State", record["state"] or "—")

    st.metric("Notes", record["notes"] or "—")

    st.divider()
    st.metric(
        "Formulas using this ingredient",
        "0",
        help="Placeholder — the Formulas module is not implemented yet.",
    )

    st.divider()
    st.write("**Custom fields**")
    custom_df = custom_fields_to_df(record["custom_fields"])
    if custom_df.empty:
        st.caption("No custom fields.")
    else:
        st.dataframe(custom_df, hide_index=True, width="stretch")

    b1, b2 = st.columns(2)
    if b1.button("✏️ Edit", use_container_width=True, key=f"edit_{record['id']}"):
        st.session_state.ingredients_mode = record["id"]
        st.session_state.ingredients_confirm_delete_id = None
        st.rerun()
    if b2.button("🗑️ Delete", use_container_width=True, key=f"del_{record['id']}"):
        st.session_state.ingredients_confirm_delete_id = record["id"]
        st.rerun()


def _render_delete_confirm(conn, record_id: int) -> None:
    record = gw.get_ingredient(conn, record_id)
    if record is None:
        st.warning("The selected ingredient no longer exists.")
        st.session_state.ingredients_confirm_delete_id = None
        return
    st.warning(
        f"Delete **{record['name']}** (ID {record_id})? This cannot be undone."
    )
    c1, c2 = st.columns(2)
    if c1.button(
        "Confirm delete", type="primary", key=f"confirm_del_{record_id}"
    ):
        try:
            gw.delete_ingredient(conn, record_id)
        except gw.GatewayError as exc:
            st.error(f"Delete failed: {exc}")
        else:
            st.session_state.ingredients_selected_id = None
            _reset_to_details()
            st.rerun()
    if c2.button("Cancel", key=f"cancel_del_{record_id}"):
        _reset_to_details()
        st.rerun()


def _render_edit_form(conn, record: dict | None) -> None:
    """Create form (record=None) or edit form (record=dict)."""
    is_edit = record is not None
    record = record or {}
    record_id = record.get("id", "new")

    with st.form(f"ingredient_form_{record_id}"):
        st.markdown(f"### {'Edit ingredient' if is_edit else 'New ingredient'}")
        name = st.text_input(
            "Name *",
            value=record.get("name", ""),
            placeholder="Preferred display name",
        )
        item_code = st.text_input(
            "Item code",
            value=record.get("item_code") or "",
            help="From the external item-code system (optional)",
        )
        item_description = st.text_area(
            "Item description", value=record.get("item_description") or ""
        )
        supplier = st.text_input("Supplier", value=record.get("supplier") or "")
        notes = st.text_area("Notes", value=record.get("notes") or "")

        c1, c2 = st.columns(2)
        uom = c1.text_input(
            "UOM", value=record.get("uom") or "", help="Default unit (optional)"
        )
        state_index = 0
        if record.get("state") in INGREDIENT_STATES:
            state_index = INGREDIENT_STATES.index(record["state"]) + 1
        state = c2.selectbox(
            "State",
            [None, *INGREDIENT_STATES],
            index=state_index,
            format_func=lambda s: "— not set —" if s is None else s,
        )

        st.write("**Custom fields**")
        st.caption("Free key/value properties (user-defined names).")
        custom_editor = st.data_editor(
            custom_fields_to_df(record.get("custom_fields")),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            column_config={
                "key": st.column_config.TextColumn("Key", required=False),
                "value": st.column_config.TextColumn("Value"),
            },
            key=f"custom_fields_{record_id}",
        )
        submitted = st.form_submit_button("Save", type="primary")

    if st.button("Cancel", key=f"cancel_{record_id}"):
        _reset_to_details()
        st.rerun()

    if submitted:
        payload = build_ingredient_payload(
            name=name,
            item_code=item_code,
            item_description=item_description,
            supplier=supplier,
            notes=notes,
            uom=uom,
            state=state,
            custom_fields=custom_fields_from_df(custom_editor),
        )
        try:
            # st.toast survives the rerun below (st.success would not).
            if is_edit:
                gw.update_ingredient(conn, record["id"], payload)
                st.toast("Ingredient updated.")
            else:
                gw.create_ingredient(conn, payload)
                st.toast("Ingredient created.")
        except gw.GatewayError as exc:
            problems = exc.problems or [str(exc)]
            st.error("Could not save ingredient:\n- " + "\n- ".join(problems))
        else:
            _reset_to_details()
            st.rerun()


# ---------------------------------------------------------------- layout
left, right = st.columns([3, 1], gap="small")

with left:
    if df.empty:
        st.info("No ingredients yet — add your first one.")
    else:
        # Lean table: internal id, item code, item description and custom
        # fields stay visible in the Details panel only
        # (frontend/ingredients/README.md §4).
        table_df = df.drop(
            columns=["id", "item_code", "item_description", "custom_fields"]
        )
        event = st.dataframe(
            table_df,
            height="content",
            hide_index=True,
            selection_mode="single-row",
            on_select="rerun",
            key="ingredients_table",
            width="stretch",
        )
        rows = event.selection.rows
        if rows:
            st.session_state.ingredients_selected_id = int(df.iloc[rows[0]]["id"])

with right:
    st.subheader("Details")

    mode = st.session_state.ingredients_mode

    if mode == "create":
        _render_edit_form(conn, record=None)
    elif isinstance(mode, int):
        record = gw.get_ingredient(conn, mode)
        if record is None:
            st.warning("The ingredient you were editing no longer exists.")
            st.session_state.ingredients_selected_id = None
            _reset_to_details()
        else:
            _render_edit_form(conn, record)
    elif st.session_state.ingredients_confirm_delete_id is not None:
        _render_delete_confirm(conn, st.session_state.ingredients_confirm_delete_id)
    else:
        _render_details(conn, st.session_state.ingredients_selected_id)
