"""Test Reports detail page (hidden child page, README §4).

Reads the report id from the query params (?report_id=3), falling back to
session_state so AppTest can drive it headlessly. Renders the tabs from
README §4: Overview and Results. (An Analysis tab is reserved for the
future per-template charts and is deliberately not rendered in v0.)
Reached via st.switch_page from the overview.

A report is one evaluation event; its Results tab lists one row per
evaluated sample, each anchored to a sample and one of that sample's
transfers. Results are added/edited/deleted here.
"""
import pandas as pd
import streamlit as st

from backend.gateway import test_reports as gw
from backend.services.test_reports.store import DEV_DB_PATH

from frontend.common import configure_page, show_pending_notification
from frontend.test_reports.dialogs import (
    add_result_dialog,
    delete_dialog,
    delete_result_dialog,
    edit_dialog,
    edit_result_dialog,
)
from frontend.test_reports.relations import sample_index, transfer_index
from frontend.test_reports.utils import result_rows

configure_page()

# ------------------------------------------------------------------ data
if "test_reports_conn" not in st.session_state:
    st.session_state.test_reports_conn = gw.connect(DEV_DB_PATH)
conn = st.session_state.test_reports_conn

back_col, _ = st.columns([5, 1], vertical_alignment="center")
with back_col:
    if st.button("← Back to overview", key="back_overview"):
        # switch_page clears query params on navigation (report_id included).
        st.switch_page("test_reports/app.py")

raw_id = st.query_params.get("report_id")
if raw_id is None:
    raw_id = st.session_state.get("test_reports_detail_id")
try:
    report_id = int(raw_id) if raw_id else None
except (TypeError, ValueError):
    report_id = None

if report_id is None:
    st.info("No report selected — go back to the overview and open one.")
    st.stop()

record = gw.get_report(conn, report_id)
if record is None:
    st.warning("This test report no longer exists.")
    st.stop()

results = gw.list_results(conn, record["id"])

# ----------------------------------------------------------------- header
title_col, actions_col = st.columns([5, 1], vertical_alignment="center")
with title_col:
    st.title(record.get("test_method") or "Test report")
    st.caption(
        f"Evaluated {(record.get('evaluation_date') or '')[:10]} · "
        f"in charge: {record.get('person_in_charge') or '—'}"
    )
with actions_col:
    if st.button(
        "✏️ Edit", type="primary", use_container_width=True, key="edit_detail"
    ):
        edit_dialog(conn, record)
    if st.button("🗑️ Delete", use_container_width=True, key="delete_detail"):
        delete_dialog(conn, record)

# ------------------------------------------------------------------- tabs
tab_overview, tab_results = st.tabs(["Overview", "Results"])


def _render_overview(record: dict, results: list[dict]) -> None:
    sample_ids = {result["sample_id"] for result in results}
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Evaluation date", (record.get("evaluation_date") or "")[:10])
    d2.metric("Person in charge", record.get("person_in_charge") or "—")
    d3.metric("Samples", len(sample_ids))
    d4.metric("Results", len(results))

    st.divider()
    o1, o2 = st.columns(2)
    o1.metric("Equipment", record.get("equipment") or "—")
    o2.metric("Panel", record.get("panel") or "—")
    if record.get("methodology"):
        st.markdown(f"**Methodology**\n\n{record['methodology']}")
    if record.get("notes"):
        st.markdown(f"**Notes**\n\n{record['notes']}")
    st.caption(f"Created {record.get('created_at') or '—'}")


def _render_results(record: dict, results: list[dict]) -> None:
    """One row per evaluated sample (README §4/Q6/Q7)."""
    samples = sample_index()
    transfers = transfer_index([r["sample_id"] for r in results])
    r1, r2 = st.columns(2)
    r1.metric("Results", len(results))
    r2.metric("Samples", len({r["sample_id"] for r in results}))

    if not results:
        st.info(
            "No results yet — add one row per evaluated sample. Each row "
            "is anchored to a sample and one of its transfers."
        )
    else:
        st.dataframe(
            pd.DataFrame(
                result_rows(
                    results,
                    sample_index=samples,
                    transfer_index=transfers,
                )
            ),
            hide_index=True,
            width="stretch",
        )
        labels = []
        for result in results:
            sample = samples.get(result["sample_id"]) or {}
            code = sample.get("sample_code") or f"#{result['sample_id']}"
            value = result.get("value")
            unit = result.get("unit") or ""
            labels.append(
                f"{code} · {result.get('parameter') or ''} · {value} {unit}".strip()
            )
        idx = st.selectbox(
            "Manage a result",
            range(len(results)),
            format_func=lambda i: labels[i],
            key=f"result_select_{record['id']}",
        )
        selected = results[idx]
        e1, e2 = st.columns(2)
        if e1.button("✏️ Edit result", use_container_width=True):
            edit_result_dialog(conn, record, selected)
        if e2.button("🗑️ Delete result", use_container_width=True):
            delete_result_dialog(conn, record, selected)

    st.divider()
    if st.button("➕ Add result", type="primary", key="add_result"):
        add_result_dialog(conn, record)


# ---------------------------------------------------------------- sections
with tab_overview:
    _render_overview(record, results)
with tab_results:
    _render_results(record, results)

# A write outcome (report or result dialog) may be pending in
# session_state — render it. Only one dialog can be open per run.
show_pending_notification()
