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

from frontend.common import configure_page, show_pending_notification
from frontend.formulas.dialogs import (
    batches_connection,
    delete_dialog,
    duplicate_dialog,
    form_dialog,
)
from frontend.formulas.utils import FORMULAS_TABLE_KEY, formula_stats
from backend.gateway import batches as bgw

configure_page()

# ------------------------------------------------------------------ data
if "formulas_conn" not in st.session_state:
    st.session_state.formulas_conn = gw.connect(DEV_DB_PATH)
conn = st.session_state.formulas_conn

# Header row: page title left, primary "Add" button top-right.
title_col, add_col = st.columns([5, 1], vertical_alignment="center")
with title_col:
    st.title("Formulas")
    st.caption(
        "Batches made from a formula snapshot that formula's composition "
        "at creation, scaled to each batch's target yield. Editing the "
        "formula later never changes its existing batches."
    )
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

# Real "batches made from this formula" counts come from the Batches
# service (README §6 — reverse link; one GROUP BY call for the table).
try:
    batches_by_formula = bgw.count_batches_by_formula_id(batches_connection())
except bgw.GatewayError as exc:
    st.error(f"Could not load related batches: {exc}")
    batches_by_formula = {}

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
                "batches": batches_by_formula.get(record["id"], 0),
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
        key=FORMULAS_TABLE_KEY,
        width="stretch",
        # id stays in df (selection maps back via df.iloc[idx]["id"]) but
        # is hidden from the rendered table (README Q14-style polish).
        column_config={"id": None},
    )

    selected_id = None
    if event.selection.rows and event.selection.rows[0] < len(df):
        # The selection can survive a delete one index past the end of the
        # now-smaller table (frontend keeps the stale row index); guard it.
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
                # switch_page clears existing query params on navigation, so
                # the formula id must travel via its query_params argument
                # (st.query_params set before the switch would be wiped).
                st.switch_page(
                    "formulas/detail.py",
                    query_params={"formula_id": str(record["id"])},
                )
            if c2.button("✏️ Edit", use_container_width=True):
                form_dialog(conn, record)
            if c3.button("📋 Duplicate", use_container_width=True):
                duplicate_dialog(conn, record)
            if c4.button("🗑️ Delete", use_container_width=True):
                delete_dialog(conn, record)

# Show any queued write outcome (create/update/delete/duplicate) from this run.
show_pending_notification()
