"""Samples page — overview (Lab section).

Shows all samples with their attributes and stats (frontend/samples/
README.md §2, §4): code, origin (batch or benchmark), status, taken date,
age in weeks, dispatch count and test-report count. Create/edit/delete
launch st.dialog modals; opening a sample switches to the hidden detail
page (README Q9) with the sample id in the query params.

The page stays thin glue (docs/TEST_STRATEGIES.md §5): widgets -> gateway
call -> display. Pure helpers live in utils.py; dialogs in dialogs.py;
service + gateway live in backend/.
"""
import pandas as pd
import streamlit as st

from backend.gateway import samples as gw
from backend.services.samples.schema import SAMPLE_STATUSES
from backend.services.samples.store import DEV_DB_PATH

from frontend.common import configure_page, show_pending_notification
from frontend.samples.dialogs import create_dialog, delete_dialog, edit_dialog
from frontend.samples.relations import batch_index, report_counts_by_sample
from frontend.samples.utils import (
    SAMPLES_TABLE_KEY,
    batch_options,
    filter_samples,
    overview_rows,
)

configure_page()

# ------------------------------------------------------------------ data
if "samples_conn" not in st.session_state:
    st.session_state.samples_conn = gw.connect(DEV_DB_PATH)
conn = st.session_state.samples_conn

# Header row: page title left, primary "Add" button top-right.
title_col, add_col = st.columns([5, 1], vertical_alignment="center")
with title_col:
    st.title("Samples")
    st.caption(
        "Samples are what the lab sends out and tests: each carries its "
        "batch's identity everywhere it goes (formula → batch → sample → "
        "test report). A sample is either batch-born or a standalone "
        "benchmark."
    )
with add_col:
    if st.button(
        "➕ Add sample",
        type="primary",
        use_container_width=True,
        key="add_sample",
    ):
        create_dialog(conn)

try:
    records = gw.list_samples(conn)
except gw.GatewayError as exc:
    st.error(f"Could not load samples: {exc}")
    records = []

# Reverse link to the Batches service (README §6): real batch codes for
# the origin column/links and the batch filter.
batches_by_id = batch_index()

try:
    transfer_counts = gw.transfer_counts_by_sample_id(conn)
except gw.GatewayError as exc:
    st.error(f"Could not load transfer counts: {exc}")
    transfer_counts = {}

# Reverse link to the Test Reports service (README §6): real per-sample
# report counts for the overview column.
report_counts = report_counts_by_sample()

# ------------------------------------------------------------------ filters
status_filter = "All"
batch_filter_id = None
if records:
    f1, f2 = st.columns(2)
    status_filter = f1.selectbox(
        "Status", ["All", *SAMPLE_STATUSES], key="samples_status_filter"
    )
    batch_ids = sorted(
        {
            record["batch_id"]
            for record in records
            if record.get("origin") == "batch"
            and record.get("batch_id") is not None
        }
    )
    if batch_ids:
        labels, label_to_id = batch_options(
            [batches_by_id[bid] for bid in batch_ids if bid in batches_by_id]
        )
        if labels:
            batch_label = f2.selectbox(
                "Batch", ["All batches", *labels], key="samples_batch_filter"
            )
            if batch_label != "All batches":
                batch_filter_id = label_to_id.get(batch_label)

filtered = filter_samples(
    records,
    status=None if status_filter == "All" else status_filter,
    batch_id=batch_filter_id,
)

# ------------------------------------------------------------------- table
if not records:
    st.info(
        "No samples yet — create a batch-born sample or record a benchmark."
    )
elif not filtered:
    st.info("No samples match the current filters.")
else:
    df = pd.DataFrame(
        overview_rows(
            filtered,
            batch_index=batches_by_id,
            transfer_counts=transfer_counts,
            report_counts=report_counts,
        )
    )
    event = st.dataframe(
        df,
        height="content",
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key=SAMPLES_TABLE_KEY,
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
        st.caption("Select a sample to open, edit or delete it.")
    else:
        record = next((r for r in records if r["id"] == selected_id), None)
        if record is None:
            st.caption("Select a sample to open, edit or delete it.")
        else:
            c1, c2, c3 = st.columns(3)
            if c1.button(
                "Open detail", type="primary", use_container_width=True
            ):
                # switch_page clears existing query params on navigation, so
                # the sample id must travel via its query_params argument
                # (st.query_params set before the switch would be wiped).
                st.switch_page(
                    "samples/detail.py",
                    query_params={"sample_id": str(record["id"])},
                )
            if c2.button("✏️ Edit", use_container_width=True):
                edit_dialog(conn, record)
            if c3.button("🗑️ Delete", use_container_width=True):
                delete_dialog(conn, record)

# A write outcome (create/edit/delete dialog) may be pending in
# session_state — render it. Only one dialog can be open per run; no other
# dialog is open here.
show_pending_notification()
