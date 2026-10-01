"""Batches page — overview (Lab section).

Shows all batches with their attributes and stats (frontend/batches/
README.md §1, §4); create/edit/delete launch st.dialog modals; opening a
batch switches to the hidden detail page (README Q7) with the batch id in
the query params.

The page stays thin glue (docs/TEST_STRATEGIES.md §5): widgets -> gateway
call -> display. Pure helpers live in utils.py; dialogs in dialogs.py;
service + gateway live in backend/.
"""
import pandas as pd
import streamlit as st

from backend.gateway import batches as gw
from backend.services.batches.store import DEV_DB_PATH

from frontend.batches.dialogs import create_dialog, delete_dialog, edit_dialog
from frontend.batches.relations import (
    report_counts_by_batch,
    sample_counts_by_batch,
)
from frontend.batches.utils import BATCHES_TABLE_KEY, batch_stats
from frontend.common import configure_page, show_pending_notification

configure_page()

# ------------------------------------------------------------------ data
if "batches_conn" not in st.session_state:
    st.session_state.batches_conn = gw.connect(DEV_DB_PATH)
conn = st.session_state.batches_conn

# Header row: page title left, primary "Add" button top-right.
title_col, add_col = st.columns([5, 1], vertical_alignment="center")
with title_col:
    st.title("Batches")
    st.caption(
        "Each batch's planned composition is a snapshot of its source "
        "formula at creation — scaled to the batch's target yield and "
        "frozen there. Editing the formula later never changes existing "
        "batches."
    )
with add_col:
    if st.button(
        "➕ Add batch",
        type="primary",
        use_container_width=True,
        key="add_batch",
    ):
        create_dialog(conn)

try:
    records = gw.list_batches(conn)
except gw.GatewayError as exc:
    st.error(f"Could not load batches: {exc}")
    records = []

# Reverse links to the Samples and Test Reports services (README §6):
# real sample and test-report counts for the overview stats and guards.
samples_by_batch = sample_counts_by_batch()
reports_by_batch = report_counts_by_batch()

if not records:
    st.info("No batches yet — create one from a formula.")
else:
    # Lean table: heavy JSON columns stay in the detail page
    # (frontend/batches/README.md §4).
    rows = []
    for record in records:
        stats = batch_stats(
            record,
            sample_count=samples_by_batch.get(record["id"], 0),
            report_count=reports_by_batch.get(record["id"], 0),
        )
        rows.append(
            {
                "id": record["id"],
                "code": record["batch_code"],
                "name": record["name"],
                "formula": record["formula_name"],
                "status": record["status"],
                "updated": (record["updated_at"] or "")[:10],
                "samples": stats["samples"],
                "reports": stats["reports"],
            }
        )
    df = pd.DataFrame(rows)

    event = st.dataframe(
        df,
        height="content",
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key=BATCHES_TABLE_KEY,
        width="stretch",
        # id stays in df (selection maps back via df.iloc[idx]["id"]) but
        # is hidden from the rendered table.
        column_config={"id": None},
    )

    selected_id = None
    if event.selection.rows and event.selection.rows[0] < len(df):
        # The selection can survive a delete one index past the end of the
        # now-smaller table (frontend keeps the stale row index); guard it.
        selected_id = int(df.iloc[event.selection.rows[0]]["id"])

    if selected_id is None:
        st.caption("Select a batch to open, edit or delete it.")
    else:
        record = next((r for r in records if r["id"] == selected_id), None)
        if record is None:
            st.caption("Select a batch to open, edit or delete it.")
        else:
            c1, c2, c3 = st.columns(3)
            if c1.button(
                "Open detail", type="primary", use_container_width=True
            ):
                # switch_page clears existing query params on navigation, so
                # the batch id must travel via its query_params argument
                # (st.query_params set before the switch would be wiped).
                st.switch_page(
                    "batches/detail.py",
                    query_params={"batch_id": str(record["id"])},
                )
            if c2.button("✏️ Edit", use_container_width=True):
                edit_dialog(conn, record)
            if c3.button("🗑️ Delete", use_container_width=True):
                delete_dialog(conn, record)

# A write outcome (create/edit/delete dialog) may be pending in
# session_state — render it. Only one dialog can be open per run; no other
# dialog is open here.
show_pending_notification()
