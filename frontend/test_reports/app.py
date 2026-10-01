"""Test Reports page — overview (Lab section).

Shows all test reports with their attributes and stats
(frontend/test_reports/README.md §2, §4): method, evaluation date,
person-in-charge, sample/result counts. Create/edit/delete launch
st.dialog modals; opening a report switches to the hidden detail page
with the report id in the query params.

The page stays thin glue (docs/TEST_STRATEGIES.md §5): widgets -> gateway
call -> display. Pure helpers live in utils.py; dialogs in dialogs.py;
service + gateway live in backend/.
"""
import pandas as pd
import streamlit as st

from backend.gateway import test_reports as gw
from backend.services.test_reports.store import DEV_DB_PATH

from frontend.common import configure_page, show_pending_notification
from frontend.test_reports.dialogs import (
    create_dialog,
    delete_dialog,
    edit_dialog,
)
from frontend.test_reports.utils import REPORTS_TABLE_KEY, overview_rows

configure_page()

# ------------------------------------------------------------------ data
if "test_reports_conn" not in st.session_state:
    st.session_state.test_reports_conn = gw.connect(DEV_DB_PATH)
conn = st.session_state.test_reports_conn

# Header row: page title left, primary "Add" button top-right.
title_col, add_col = st.columns([5, 1], vertical_alignment="center")
with title_col:
    st.title("Test Reports")
    st.caption(
        "A test report is one evaluation event — sensory, shelf-life, "
        "stability or microbiology. It covers one or many samples; each "
        "sample's measured outcome is a result row."
    )
with add_col:
    if st.button(
        "➕ Add report",
        type="primary",
        use_container_width=True,
        key="add_report",
    ):
        create_dialog(conn)

try:
    records = gw.list_reports(conn)
except gw.GatewayError as exc:
    st.error(f"Could not load test reports: {exc}")
    records = []

# Sample/result counts per report — derived, never stored (README §5.2).
try:
    result_stats = gw.result_stats_by_report_id(conn)
except gw.GatewayError as exc:
    st.error(f"Could not load result counts: {exc}")
    result_stats = {}

# ------------------------------------------------------------------- table
if not records:
    st.info("No test reports yet — add your first one.")
else:
    df = pd.DataFrame(overview_rows(records, result_stats=result_stats))
    event = st.dataframe(
        df,
        height="content",
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key=REPORTS_TABLE_KEY,
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
        st.caption("Select a report to open, edit or delete it.")
    else:
        record = next((r for r in records if r["id"] == selected_id), None)
        if record is None:
            st.caption("Select a report to open, edit or delete it.")
        else:
            c1, c2, c3 = st.columns(3)
            if c1.button(
                "Open detail", type="primary", use_container_width=True
            ):
                # switch_page clears existing query params on navigation, so
                # the report id must travel via its query_params argument.
                st.switch_page(
                    "test_reports/detail.py",
                    query_params={"report_id": str(record["id"])},
                )
            if c2.button("✏️ Edit", use_container_width=True):
                edit_dialog(conn, record)
            if c3.button("🗑️ Delete", use_container_width=True):
                delete_dialog(conn, record)

# A write outcome (create/edit/delete dialog) may be pending in
# session_state — render it. Only one dialog can be open per run.
show_pending_notification()
