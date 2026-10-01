"""Samples detail page (hidden child page, README Q9).

Reads the sample id from the query params (?sample_id=3), falling back to
session_state so AppTest can drive it headlessly. Renders the three tabs
from README §4: Overview, Transfers, Test reports. Reached via
st.switch_page from the overview.

The Transfers tab is the source of truth for where a sample has been
(README Q13): the initial retention row is read-only, dispatches are
added/edited/deleted here.
"""
import pandas as pd
import streamlit as st

from backend.gateway import samples as gw
from backend.services.samples.store import DEV_DB_PATH

from frontend.common import configure_page, show_pending_notification
from frontend.samples.dialogs import (
    add_dispatch_dialog,
    delete_dialog,
    delete_dispatch_dialog,
    edit_dialog,
    edit_dispatch_dialog,
)
from frontend.samples.relations import batch_index, results_for_sample
from frontend.samples.utils import (
    dispatches,
    origin_label,
    retention,
    transfer_count,
    transfer_rows,
    weeks_since,
)
from frontend.test_reports.utils import transfer_label

configure_page()

# ------------------------------------------------------------------ data
if "samples_conn" not in st.session_state:
    st.session_state.samples_conn = gw.connect(DEV_DB_PATH)
conn = st.session_state.samples_conn

back_col, _ = st.columns([5, 1], vertical_alignment="center")
with back_col:
    if st.button("← Back to overview", key="back_overview"):
        # switch_page clears query params on navigation (sample_id included).
        st.switch_page("samples/app.py")

raw_id = st.query_params.get("sample_id")
if raw_id is None:
    raw_id = st.session_state.get("samples_detail_id")
try:
    sample_id = int(raw_id) if raw_id else None
except (TypeError, ValueError):
    sample_id = None

if sample_id is None:
    st.info("No sample selected — go back to the overview and open one.")
    st.stop()

record = gw.get_sample(conn, sample_id)
if record is None:
    st.warning("This sample no longer exists.")
    st.stop()

transfers = gw.list_transfers(conn, record["id"])
batches_by_id = batch_index()

# ----------------------------------------------------------------- header
title_col, actions_col = st.columns([5, 1], vertical_alignment="center")
with title_col:
    st.title(record["sample_code"])
    st.caption(
        f"{origin_label(record, batches_by_id)} · status: {record['status']}"
    )
with actions_col:
    if st.button(
        "✏️ Edit", type="primary", use_container_width=True, key="edit_detail"
    ):
        edit_dialog(conn, record)
    if st.button("🗑️ Delete", use_container_width=True, key="delete_detail"):
        delete_dialog(conn, record)

# ------------------------------------------------------------------- tabs
tab_overview, tab_transfers, tab_reports = st.tabs(
    ["Overview", "Transfers", "Test reports"]
)


def _render_overview(record: dict) -> None:
    weeks = weeks_since(record["taken_at"])
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Taken", record.get("taken_at") or "—")
    d2.metric("Age", f"{weeks} wk" if weeks is not None else "—")
    d3.metric("Status", record["status"])
    d4.metric(
        "Dispatches",
        transfer_count(transfers, kind="dispatch"),
        help="How many times this sample has been sent to another team.",
    )

    st.divider()
    st.write("**Origin**")
    if record.get("origin") == "benchmark":
        st.metric("Benchmark source", record.get("source") or "—")
    else:
        batch = batches_by_id.get(record.get("batch_id")) or {}
        o1, o2, o3 = st.columns(3)
        o1.metric("Batch", batch.get("batch_code") or f"#{record.get('batch_id')}")
        o2.metric("Batch name", batch.get("name") or "—")
        o3.metric(
            "Formula",
            f"{batch['formula_name']} v{batch['formula_version']}"
            if batch.get("formula_name")
            else "—",
        )
        if batch:
            if st.button("Open batch in Lab", key="open_batch"):
                st.switch_page(
                    "batches/detail.py",
                    query_params={"batch_id": str(record["batch_id"])},
                )

    if record.get("notes"):
        st.markdown(f"**Notes**\n\n{record['notes']}")
    st.caption(f"Created {record.get('created_at') or '—'}")


def _render_transfers(record: dict) -> None:
    """Newest-first transfer history (README §4/Q6/Q7)."""
    row = retention(transfers)
    if row is not None:
        st.write("**Retention (in-house)**")
        st.caption(
            "Created with the sample and read-only — it anchors every test "
            "report to a transfer (README Q7)."
        )
        r1, r2, r3 = st.columns(3)
        r1.metric("Storage condition", row.get("storage_condition") or "—")
        r2.metric("Since", row.get("sent_at") or "—")
        r3.metric("Sent by", row.get("sent_by") or "—")
    else:
        st.warning(
            "This sample has no retention transfer — it should always have "
            "one (README Q7)."
        )

    st.divider()
    st.write("**Transfer history**")
    if not transfers:
        st.info("No transfers recorded.")
        return
    st.dataframe(
        transfer_rows(transfers),
        hide_index=True,
        width="stretch",
    )

    dispatch_list = dispatches(transfers)
    if not dispatch_list:
        st.caption(
            "No dispatches yet — the sample has not been sent to another "
            "team."
        )
    else:
        labels = [
            f"{t.get('to_team') or '?'} · {t.get('sent_at') or '—'}"
            for t in dispatch_list
        ]
        idx = st.selectbox(
            "Manage a dispatch",
            range(len(dispatch_list)),
            format_func=lambda i: labels[i],
            key=f"dispatch_select_{record['id']}",
        )
        selected = dispatch_list[idx]
        e1, e2 = st.columns(2)
        if e1.button("✏️ Edit dispatch", use_container_width=True):
            edit_dispatch_dialog(conn, record, selected)
        if e2.button("🗑️ Delete dispatch", use_container_width=True):
            delete_dispatch_dialog(conn, record, selected)

    st.divider()
    if st.button("➕ Dispatch to a team", type="primary", key="add_dispatch"):
        add_dispatch_dialog(conn, record)


def _render_reports(record: dict, transfers: list[dict]) -> None:
    """Test reports / results for this sample (Test Reports reverse link,
    README §6). One report may cover several samples; every result here is
    anchored to this sample and one of its transfers (Test Reports Q7)."""
    results = results_for_sample(record["id"])
    report_ids = {row["report_id"] for row in results}
    r1, r2 = st.columns(2)
    r1.metric("Test reports", len(report_ids))
    r2.metric("Results", len(results))
    if not results:
        st.info(
            "No test reports for this sample yet — results recorded on the "
            "Test Reports page appear here."
        )
        return

    transfer_by_id = {transfer["id"]: transfer for transfer in transfers}
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "date": (row.get("evaluation_date") or "")[:10],
                    "method": row.get("test_method") or "",
                    "transfer": transfer_label(
                        transfer_by_id.get(row.get("transfer_id"))
                    ),
                    "parameter": row.get("parameter") or "",
                    "value": row.get("value"),
                    "unit": row.get("unit") or "",
                }
                for row in results
            ]
        ),
        hide_index=True,
        width="stretch",
    )

    # One row per report, so the user can open it (a report may cover
    # several samples and several results of this one).
    reports = {}
    for row in results:
        reports.setdefault(
            row["report_id"],
            {
                "id": row["report_id"],
                "method": row.get("test_method") or "",
                "date": (row.get("evaluation_date") or "")[:10],
            },
        )
    report_list = list(reports.values())
    labels = [f"{r['date']} · {r['method']}" for r in report_list]
    open_col, _ = st.columns([2, 3])
    with open_col:
        index = st.selectbox(
            "Open a report",
            range(len(report_list)),
            format_func=lambda i: labels[i],
            key=f"sample_report_{record['id']}",
        )
        if st.button("Open report detail", type="primary"):
            st.switch_page(
                "test_reports/detail.py",
                query_params={"report_id": str(report_list[index]["id"])},
            )


# ---------------------------------------------------------------- sections
with tab_overview:
    _render_overview(record)
with tab_transfers:
    _render_transfers(record)
with tab_reports:
    _render_reports(record, transfers)

# A write outcome (dispatch or sample edit/delete dialog) may be pending in
# session_state — render it. Only one dialog can be open per run; no other
# dialog is open here.
show_pending_notification()
