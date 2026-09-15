"""Shared dialogs for the Samples pages (overview and detail).

st.dialog modals per README §7 — one implementation, launched from both
entry points. Pages stay thin glue (docs/TEST_STRATEGIES.md §5): the
dialogs call the gateway directly and reuse the pure helpers in utils.py.

The create dialog reads the Batches service (in-process connection) to
pick the batch a batch-born sample comes from — the same pattern the
Batches create dialog uses to read Formulas.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st

from backend.gateway import samples as gw
from backend.services.samples.schema import (
    SAMPLE_ORIGINS,
    SAMPLE_STATUSES,
    STORAGE_CONDITIONS,
)

from frontend.common import notify
from frontend.samples.relations import batch_index
from frontend.samples.utils import (
    SAMPLES_TABLE_KEY,
    batch_options,
    build_sample_payload,
    build_transfer_payload,
    normalize_sample_code,
    parse_date,
    sample_delete_block_reason,
    suggest_sample_code,
    transfer_count,
)

_NEW_CODE_KEY = "samples_new_code"

_ORIGIN_LABELS = {
    "batch": "From a batch",
    "benchmark": "Benchmark (market sample)",
}


def _existing_codes(conn: Any) -> list[str]:
    try:
        return [record["sample_code"] for record in gw.list_samples(conn)]
    except gw.GatewayError as exc:
        st.error(f"Could not load samples: {exc}")
        return []


def _load_batches() -> list[dict]:
    """Batch records for the origin picker (via the Batches service)."""
    return list(batch_index().values())


def _regenerate_code(conn: Any) -> None:
    """Suggest a fresh sample code (README Q3/Q11).

    Runs as an ``on_click`` callback: it fires before the next script run
    instantiates the code widget, so Streamlit allows the assignment.
    Assigning inside the button body instead would raise
    ``StreamlitAPIException`` — the widget with that key already exists in
    the current run.
    """
    st.session_state[_NEW_CODE_KEY] = suggest_sample_code(
        _existing_codes(conn)
    )


@st.dialog("New sample", width="medium")
def create_dialog(conn: Any) -> None:
    """Create a sample (README Q1/Q3/Q7/Q11).

    A sample is either batch-born (batch required) or a standalone
    benchmark. The code is suggested and confirmable/overridable, and the
    initial retention transfer's storage condition is chosen here.
    """
    st.markdown("### New sample")
    with st.expander("How samples work"):
        st.markdown(
            "A sample is the Lab's atomic unit; the traceability chain is "
            "**formula → batch → sample → test report**.\n\n"
            "- **Origin** — from a batch, or a standalone **benchmark** "
            "(e.g. a market product).\n"
            "- **Sample code** — a unique 3-character code. One is "
            "suggested; confirm it or type your own. It is frozen after "
            "creation.\n"
            "- **Retention transfer** — every sample gets one in-house "
            "*retention* record with a storage condition. It is read-only "
            "and anchors the sample's future test reports.\n"
            "- **Dispatches** — sending the sample to another team "
            "(shelf-life, microbiology) is recorded later, on the detail "
            "page's **Transfers** tab. A dispatched sample cannot be "
            "deleted."
        )
    batches = _load_batches()
    options, label_to_id = batch_options(batches)

    origin = st.radio(
        "Origin",
        SAMPLE_ORIGINS,
        horizontal=True,
        format_func=lambda value: _ORIGIN_LABELS.get(value, value),
    )

    batch_label = None
    if origin == "batch":
        if not options:
            st.warning(
                "No batches yet — create one on the Batches page first, or "
                "record a benchmark sample."
            )
        else:
            batch_label = st.selectbox("Batch *", options)

    source = ""
    if origin == "benchmark":
        source = st.text_input(
            "Source", placeholder="Supplier / brand (optional)"
        )

    if _NEW_CODE_KEY not in st.session_state:
        st.session_state[_NEW_CODE_KEY] = suggest_sample_code(
            _existing_codes(conn)
        )
    code_col, regen_col = st.columns([3, 1], vertical_alignment="bottom")
    code_col.text_input(
        "Sample code *",
        key=_NEW_CODE_KEY,
        max_chars=3,
        help="3 characters (A–Z, 0–9); ambiguous characters are excluded.",
    )
    regen_col.button(
        "🔄 Suggest another",
        key="regen_sample_code",
        on_click=_regenerate_code,
        args=(conn,),
    )

    taken = st.date_input("Taken date *", value=date.today())
    status = st.selectbox(
        "Status",
        SAMPLE_STATUSES,
        index=SAMPLE_STATUSES.index("active"),
    )
    storage = st.selectbox(
        "Retention storage condition *",
        STORAGE_CONDITIONS,
        help=(
            "Set once at creation and read-only afterwards; it anchors "
            "the sample's test reports."
        ),
    )
    notes = st.text_area("Notes")

    c1, c2 = st.columns(2)
    if c1.button("Create sample", type="primary"):
        batch_id = label_to_id.get(batch_label) if origin == "batch" else None
        if origin == "batch" and batch_id is None:
            st.error("Pick a batch, or switch to a benchmark sample.")
            return
        payload = build_sample_payload(
            sample_code=normalize_sample_code(
                st.session_state.get(_NEW_CODE_KEY, "")
            ),
            origin=origin,
            batch_id=batch_id,
            source=source,
            taken_at=taken.isoformat(),
            status=status,
            notes=notes,
            retention_storage=storage,
        )
        try:
            gw.create_sample(conn, payload)
        except gw.GatewayError as exc:
            problems = exc.problems or [str(exc)]
            st.error("Could not create sample:\n- " + "\n- ".join(problems))
        else:
            notify(True, "Sample created.")
            st.session_state.pop(_NEW_CODE_KEY, None)
            st.rerun()
    if c2.button("Cancel", key="cancel_create"):
        st.session_state.pop(_NEW_CODE_KEY, None)
        st.rerun()


@st.dialog("Edit sample", width="medium")
def edit_dialog(conn: Any, record: dict) -> None:
    """Edit a sample's mutable fields. Code and provenance are frozen
    after creation (README Q11/Q14); the retention row is edited nowhere
    (it is read-only, Q7)."""
    st.markdown(f"### Edit {record['sample_code']}")
    st.caption(
        "Code and origin are frozen after creation. The retention storage "
        "condition is set at creation and is read-only."
    )

    taken = st.date_input(
        "Taken date *",
        value=parse_date(record.get("taken_at")) or date.today(),
    )
    status_index = (
        SAMPLE_STATUSES.index(record["status"])
        if record.get("status") in SAMPLE_STATUSES
        else 0
    )
    status = st.selectbox("Status", SAMPLE_STATUSES, index=status_index)
    source = st.text_input("Source", value=record.get("source") or "")
    notes = st.text_area("Notes", value=record.get("notes") or "")

    c1, c2 = st.columns(2)
    if c1.button("Save", type="primary"):
        payload = {
            "taken_at": taken.isoformat(),
            "status": status,
            "source": source.strip() or None,
            "notes": notes.strip() or None,
        }
        try:
            gw.update_sample(conn, record["id"], payload)
        except gw.GatewayError as exc:
            problems = exc.problems or [str(exc)]
            st.error("Could not save sample:\n- " + "\n- ".join(problems))
        else:
            notify(True, "Sample updated.")
            st.rerun()
    if c2.button("Cancel", key="cancel_edit"):
        st.rerun()


@st.dialog("Delete sample")
def delete_dialog(conn: Any, record: dict) -> None:
    """Delete confirmation (README Q8/Q12).

    Deletion is blocked by test reports (placeholder until that module
    lands) or any dispatch; the retention row never blocks.
    """
    try:
        transfers = gw.list_transfers(conn, record["id"])
    except gw.GatewayError as exc:
        st.error(f"Could not load transfers: {exc}")
        transfers = []
    dispatch_count = transfer_count(transfers, kind="dispatch")
    reason = sample_delete_block_reason(dispatch_count, 0)

    if reason:
        st.warning(
            f"**{record['sample_code']}** cannot be deleted — {reason} "
            "Dispatched samples keep their traceability (README Q12)."
        )
        if st.button("Close", key="cancel_delete_blocked"):
            st.rerun()
        return

    st.warning(
        f"Delete **{record['sample_code']}**? This cannot be undone. It has "
        "no dispatches or test reports, so deletion is safe."
    )
    c1, c2 = st.columns(2)
    if c1.button("Confirm delete", type="primary"):
        try:
            gw.delete_sample(conn, record["id"])
        except gw.GatewayError as exc:
            st.error(f"Delete failed: {exc}")
        else:
            notify(True, "Sample deleted.")
            # The deleted row was selected; drop the stale selection so the
            # overview table does not keep an out-of-bounds index on rerun.
            if SAMPLES_TABLE_KEY in st.session_state:
                st.session_state[SAMPLES_TABLE_KEY] = {"selection": {"rows": []}}
            st.switch_page("samples/app.py")
    if c2.button("Cancel", key="cancel_delete"):
        st.rerun()


@st.dialog("Dispatch sample", width="medium")
def add_dispatch_dialog(conn: Any, record: dict) -> None:
    """Record a handoff to another team (README Q6/Q7)."""
    st.markdown(f"### Dispatch {record['sample_code']}")
    with st.form(f"dispatch_form_{record['id']}"):
        team = st.text_input(
            "To team *", placeholder="e.g. shelf-life, microbiology"
        )
        sent = st.date_input("Sent date *", value=date.today())
        storage = st.selectbox("Storage condition *", STORAGE_CONDITIONS)
        sent_by = st.text_input("Sent by")
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Add dispatch", type="primary")

    if st.button("Cancel", key=f"cancel_dispatch_{record['id']}"):
        st.rerun()

    if submitted:
        payload = build_transfer_payload(
            to_team=team,
            sent_at=sent.isoformat(),
            storage_condition=storage,
            sent_by=sent_by,
            notes=notes,
        )
        try:
            gw.create_transfer(conn, record["id"], payload)
        except gw.GatewayError as exc:
            problems = exc.problems or [str(exc)]
            st.error("Could not add dispatch:\n- " + "\n- ".join(problems))
        else:
            notify(True, "Dispatch added.")
            st.rerun()


@st.dialog("Edit dispatch", width="medium")
def edit_dispatch_dialog(conn: Any, record: dict, transfer: dict) -> None:
    """Edit a dispatch's event fields (README Q7)."""
    st.markdown(f"### Edit dispatch — {record['sample_code']}")
    with st.form(f"edit_dispatch_form_{transfer['id']}"):
        team = st.text_input("To team *", value=transfer.get("to_team") or "")
        sent = st.date_input(
            "Sent date *",
            value=parse_date(transfer.get("sent_at")) or date.today(),
        )
        storage_index = (
            STORAGE_CONDITIONS.index(transfer["storage_condition"])
            if transfer.get("storage_condition") in STORAGE_CONDITIONS
            else 0
        )
        storage = st.selectbox(
            "Storage condition *", STORAGE_CONDITIONS, index=storage_index
        )
        sent_by = st.text_input("Sent by", value=transfer.get("sent_by") or "")
        notes = st.text_area("Notes", value=transfer.get("notes") or "")
        submitted = st.form_submit_button("Save", type="primary")

    if st.button("Cancel", key=f"cancel_edit_dispatch_{transfer['id']}"):
        st.rerun()

    if submitted:
        payload = build_transfer_payload(
            to_team=team,
            sent_at=sent.isoformat(),
            storage_condition=storage,
            sent_by=sent_by,
            notes=notes,
        )
        try:
            gw.update_transfer(conn, transfer["id"], payload)
        except gw.GatewayError as exc:
            problems = exc.problems or [str(exc)]
            st.error("Could not save dispatch:\n- " + "\n- ".join(problems))
        else:
            notify(True, "Dispatch updated.")
            st.rerun()


@st.dialog("Delete dispatch")
def delete_dispatch_dialog(conn: Any, record: dict, transfer: dict) -> None:
    """Delete a dispatch (confirm). The retention row never reaches here."""
    st.warning(
        f"Delete the dispatch to **{transfer.get('to_team') or '?'}** "
        f"({transfer.get('sent_at') or '—'}) for **{record['sample_code']}**? "
        "This cannot be undone."
    )
    c1, c2 = st.columns(2)
    if c1.button("Confirm delete", type="primary"):
        try:
            gw.delete_transfer(conn, transfer["id"])
        except gw.GatewayError as exc:
            st.error(f"Delete failed: {exc}")
        else:
            notify(True, "Dispatch deleted.")
            st.rerun()
    if c2.button("Cancel", key="cancel_dispatch_delete"):
        st.rerun()
