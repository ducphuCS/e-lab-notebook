"""Formulas page — overview (Library section).

Shows all formulas with their attributes and stats (README §1, §4);
create/edit/duplicate/delete launch st.dialog modals (README Q4/Q13);
opening a formula switches to the hidden detail page (README Q5) with the
formula id in the query params.

The page stays thin glue (docs/TEST_STRATEGIES.md §5): widgets -> gateway
call -> display. Pure helpers live in utils.py; dialogs in dialogs.py;
service + gateway live in backend/.
"""
import pandas as pd
import streamlit as st

from backend.gateway import formulas as gw
from backend.services.formulas.store import DEV_DB_PATH

from frontend.common import configure_page
from frontend.formulas.dialogs import delete_dialog, duplicate_dialog, form_dialog
from frontend.formulas.utils import formula_stats

configure_page()

# ------------------------------------------------------------------ data
if "formulas_conn" not in st.session_state:
    st.session_state.formulas_conn = gw.connect(DEV_DB_PATH)
conn = st.session_state.formulas_conn

# Header row: page title left, primary "Add" button top-right.
title_col, add_col = st.columns([5, 1], vertical_alignment="center")
with title_col:
    st.title("Formulas")
with add_col:
    if st.button(
        "➕ Add formula",
        type="primary",
        use_container_width=True,
        key="add_formula",
    ):
        form_dialog(conn, None)

try:
    records = gw.list_formulas(conn)
except gw.GatewayError as exc:
    st.error(f"Could not load formulas: {exc}")
    records = []

if not records:
    st.info("No formulas yet — add your first one.")
else:
    # Lean table: heavy JSON columns stay in the detail page
    # (frontend/formulas/README.md §4).
    rows = []
    for record in records:
        stats = formula_stats(record)
        rows.append(
            {
                "id": record["id"],
                "name": record["name"],
                "project": record["project"] or "—",
                "status": record["status"],
                "family": record["family"] or "—",
                "updated": (record["updated_at"] or "")[:10],
                "ingredients": stats["ingredients"],
                "steps": stats["steps"],
                "batches": stats["batches"],
                "samples": stats["samples"],
            }
        )
    df = pd.DataFrame(rows)

    event = st.dataframe(
        df,
        height="content",
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key="formulas_table",
        width="stretch",
    )

    selected_id = None
    if event.selection.rows:
        selected_id = int(df.iloc[event.selection.rows[0]]["id"])

    if selected_id is None:
        st.caption("Select a formula to open, edit, duplicate or delete it.")
    else:
        record = next((r for r in records if r["id"] == selected_id), None)
        if record is None:
            st.caption("Select a formula to open, edit, duplicate or delete it.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            if c1.button(
                "Open detail", type="primary", use_container_width=True
            ):
                st.query_params["formula_id"] = str(record["id"])
                st.switch_page("formulas/detail.py")
            if c2.button("✏️ Edit", use_container_width=True):
                form_dialog(conn, record)
            if c3.button("📋 Duplicate", use_container_width=True):
                duplicate_dialog(conn, record)
            if c4.button("🗑️ Delete", use_container_width=True):
                delete_dialog(conn, record)
