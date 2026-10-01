"""Shared dialogs for the Test Reports pages (overview and detail).

st.dialog modals per README §7 — one implementation, launched from both
entry points. Pages stay thin glue (docs/TEST_STRATEGIES.md §5): the
dialogs call the gateway directly and reuse the pure helpers in utils.py.

The result dialog reads the Samples service (in-process connection) to
pick the evaluated sample and one of that sample's transfers — the
mirror of the Samples create dialog reading Batches.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from backend.gateway import test_reports as gw

from frontend.common import notify
from frontend.test_reports.relations import (
    sample_index,
    transfers_for_sample,
)
from frontend.test_reports.utils import (
    DEFAULT_TEST_METHOD,
    REPORTS_TABLE_KEY,
    build_report_payload,
    build_result_payload,
    parse_date,
    sample_options,
    transfer_options,
)


def _problems(exc: gw.GatewayError) -> str:
    return "\n- ".join(exc.problems or [str(exc)])


# --- report header ---------------------------------------------------------

@st.dialog("New test report", width="medium")
def create_dialog(conn: Any) -> None:
    """Create a report header (README Q15: header first, results follow)."""
    st.markdown("### New test report")
    st.caption(
        "A report is one evaluation event; its results (one row per "
        "evaluated sample) are added on the detail page."
    )
    test_method = st.text_input("Test method *", value=DEFAULT_TEST_METHOD)
    evaluation_date = st.date_input("Evaluation date *", value=date.today())
    person_in_charge = st.text_input("Person in charge")
    methodology = st.text_area("Methodology")
    equipment = st.text_input("Equipment")
    panel = st.text_input("Panel", placeholder="Sensory panel (optional)")
    notes = st.text_area("Notes")

    c1, c2 = st.columns(2)
    if c1.button("Create report", type="primary"):
        payload = build_report_payload(
            test_method=test_method,
            evaluation_date=evaluation_date.isoformat(),
            person_in_charge=person_in_charge,
            methodology=methodology,
            equipment=equipment,
            panel=panel,
            notes=notes,
        )
        try:
            gw.create_report(conn, payload)
        except gw.GatewayError as exc:
            st.error("Could not create report:\n- " + _problems(exc))
        else:
            notify(True, "Test report created.")
            st.rerun()
    if c2.button("Cancel", key="cancel_create_report"):
        st.rerun()


@st.dialog("Edit test report", width="medium")
def edit_dialog(conn: Any, record: dict) -> None:
    """Edit a report's header. Every field is mutable in v0 (README Q10)."""
    st.markdown("### Edit test report")
    test_method = st.text_input(
        "Test method *", value=record.get("test_method") or ""
    )
    evaluation_date = st.date_input(
        "Evaluation date *",
        value=parse_date(record.get("evaluation_date")) or date.today(),
    )
    person_in_charge = st.text_input(
        "Person in charge", value=record.get("person_in_charge") or ""
    )
    methodology = st.text_area(
        "Methodology", value=record.get("methodology") or ""
    )
    equipment = st.text_input("Equipment", value=record.get("equipment") or "")
    panel = st.text_input("Panel", value=record.get("panel") or "")
    notes = st.text_area("Notes", value=record.get("notes") or "")

    c1, c2 = st.columns(2)
    if c1.button("Save", type="primary"):
        payload = build_report_payload(
            test_method=test_method,
            evaluation_date=evaluation_date.isoformat(),
            person_in_charge=person_in_charge,
            methodology=methodology,
            equipment=equipment,
            panel=panel,
            notes=notes,
        )
        try:
            gw.update_report(conn, record["id"], payload)
        except gw.GatewayError as exc:
            st.error("Could not save report:\n- " + _problems(exc))
        else:
            notify(True, "Test report updated.")
            st.rerun()
    if c2.button("Cancel", key="cancel_edit_report"):
        st.rerun()


@st.dialog("Delete test report")
def delete_dialog(conn: Any, record: dict) -> None:
    """Delete a report and its results (README Q10)."""
    st.warning(
        f"Delete the test report **{record.get('test_method') or ''}** "
        f"({(record.get('evaluation_date') or '')[:10]})? Its result rows "
        "are deleted too. This cannot be undone."
    )
    c1, c2 = st.columns(2)
    if c1.button("Confirm delete", type="primary"):
        try:
            gw.delete_report(conn, record["id"])
        except gw.GatewayError as exc:
            st.error(f"Delete failed: {exc}")
        else:
            notify(True, "Test report deleted.")
            if REPORTS_TABLE_KEY in st.session_state:
                st.session_state[REPORTS_TABLE_KEY] = {
                    "selection": {"rows": []}
                }
            st.switch_page("test_reports/app.py")
    if c2.button("Cancel", key="cancel_delete_report"):
        st.rerun()


# --- results ---------------------------------------------------------------

def _index_for_id(labels: list[str], label_to_id: dict[str, int], wanted: Any) -> int:
    """Selectbox index of the option whose id equals ``wanted`` (else 0)."""
    for label, value in label_to_id.items():
        if value == wanted:
            return labels.index(label)
    return 0


def _result_fields(
    samples: list[dict],
    result: dict | None = None,
) -> dict | None:
    """Render the shared result form; return a payload-ready dict or None.

    The transfer selectbox is scoped to the chosen sample (README §7).
    Returns None when the form cannot proceed (no samples, or the picked
    sample has no transfers) so the dialog can disable its submit button.
    """
    if not samples:
        st.warning(
            "No samples yet — create a sample on the Samples page first."
        )
        return None

    sample_labels, sample_to_id = sample_options(samples)
    sample_label = st.selectbox(
        "Sample *",
        sample_labels,
        index=(
            _index_for_id(sample_labels, sample_to_id, result["sample_id"])
            if result
            else 0
        ),
    )
    sample_id = sample_to_id[sample_label]

    transfers = transfers_for_sample(sample_id)
    if not transfers:
        st.warning(
            "This sample has no transfers — every sample should have one "
            "retention row (Samples Q7)."
        )
        return None

    transfer_labels, transfer_to_id = transfer_options(transfers)
    transfer_label = st.selectbox(
        "Transfer *",
        transfer_labels,
        index=(
            _index_for_id(
                transfer_labels, transfer_to_id, result["transfer_id"]
            )
            if result
            else 0
        ),
        help="The transfer this result is anchored to (Samples Q7).",
    )

    parameter = st.text_input(
        "Parameter *",
        value=(result.get("parameter") if result else "") or "",
        placeholder="What was measured (e.g. pH, viscosity)",
    )
    value = st.number_input(
        "Value *",
        value=(
            float(result["value"])
            if result and result.get("value") is not None
            else 0.0
        ),
        format="%g",
    )
    unit = st.text_input(
        "Unit", value=(result.get("unit") if result else "") or ""
    )
    notes = st.text_area(
        "Notes", value=(result.get("notes") if result else "") or ""
    )
    return {
        "sample_id": sample_id,
        "transfer_id": transfer_to_id[transfer_label],
        "parameter": parameter,
        "value": value,
        "unit": unit,
        "notes": notes,
    }


@st.dialog("Add result", width="medium")
def add_result_dialog(conn: Any, report: dict) -> None:
    """Add one result row — one evaluated sample — to a report (Q6/Q15)."""
    st.markdown("### Add result")
    fields = _result_fields(list(sample_index().values()))

    c1, c2 = st.columns(2)
    if c1.button("Add result", type="primary", disabled=fields is None):
        if fields is None:
            return
        try:
            gw.create_result(
                conn, report["id"], build_result_payload(**fields)
            )
        except gw.GatewayError as exc:
            st.error("Could not add result:\n- " + _problems(exc))
        else:
            notify(True, "Result added.")
            st.rerun()
    if c2.button("Cancel", key="cancel_add_result"):
        st.rerun()


@st.dialog("Edit result", width="medium")
def edit_result_dialog(conn: Any, report: dict, result: dict) -> None:
    """Edit one result row."""
    st.markdown("### Edit result")
    fields = _result_fields(list(sample_index().values()), result)

    c1, c2 = st.columns(2)
    if c1.button("Save", type="primary", disabled=fields is None):
        if fields is None:
            return
        try:
            gw.update_result(
                conn, result["id"], build_result_payload(**fields)
            )
        except gw.GatewayError as exc:
            st.error("Could not save result:\n- " + _problems(exc))
        else:
            notify(True, "Result updated.")
            st.rerun()
    if c2.button("Cancel", key="cancel_edit_result"):
        st.rerun()


@st.dialog("Delete result")
def delete_result_dialog(conn: Any, report: dict, result: dict) -> None:
    """Delete one result row (confirm)."""
    st.warning(
        f"Delete the result **{result.get('parameter') or ''}** "
        f"({result.get('value')} {result.get('unit') or ''})? This cannot "
        "be undone."
    )
    c1, c2 = st.columns(2)
    if c1.button("Confirm delete", type="primary"):
        try:
            gw.delete_result(conn, result["id"])
        except gw.GatewayError as exc:
            st.error(f"Delete failed: {exc}")
        else:
            notify(True, "Result deleted.")
            st.rerun()
    if c2.button("Cancel", key="cancel_delete_result"):
        st.rerun()
