"""Page-layer cross-service reads for the Samples page.

The Samples page reads the Batches service to resolve the batch a
batch-born sample came from (code, name, formula) — the mirror of the
Formulas page reading its batches reverse link
(frontend/formulas/dialogs.py ``batches_connection``). The query lives in
the Batches service + gateway (a gateway routes to exactly one service);
this module only owns the connection.

Kept out of ``utils.py`` because it touches ``st.session_state``
(utils.py is pure, no streamlit).
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from backend.gateway import batches as bgw
from backend.gateway import test_reports as tr_gw


def batches_connection() -> Any:
    """Shared in-process connection to the Batches service.

    One connection per session, opened lazily. The dev-DB path is
    resolved at call time (not imported as a constant) so AppTest's
    per-test monkeypatched path is honoured.
    """
    from backend.services.batches import store as batches_store

    if "samples_batches_conn" not in st.session_state:
        st.session_state.samples_batches_conn = bgw.connect(
            batches_store.DEV_DB_PATH
        )
    return st.session_state.samples_batches_conn


def batch_index() -> dict[int, dict]:
    """{batch_id: batch record} for origin labels, links and the filter.

    Empty map on service failure. The overview/detail only need id, code,
    name and formula, all of which the batch record carries.
    """
    try:
        records = bgw.list_batches(batches_connection())
    except bgw.GatewayError as exc:
        st.error(f"Could not load batches: {exc}")
        return {}
    return {int(record["id"]): record for record in records}


# --- Test Reports reverse link (README §6 / Test Reports Q13) --------------

def reports_connection() -> Any:
    """Shared in-process connection to the Test Reports service.

    One connection per session, opened lazily; the dev-DB path is
    resolved at call time so AppTest's per-test monkeypatched path is
    honoured.
    """
    from backend.services.test_reports import store as reports_store

    if "samples_reports_conn" not in st.session_state:
        st.session_state.samples_reports_conn = tr_gw.connect(
            reports_store.DEV_DB_PATH
        )
    return st.session_state.samples_reports_conn


def report_counts_by_sample() -> dict[int, int]:
    """{sample_id: distinct report count} for the overview column.

    Empty map on service failure.
    """
    try:
        return tr_gw.count_reports_by_sample_id(reports_connection())
    except tr_gw.GatewayError as exc:
        st.error(f"Could not load test-report counts: {exc}")
        return {}


def results_for_sample(sample_id: int) -> list[dict]:
    """Light result summaries for a sample (Test reports tab)."""
    try:
        return tr_gw.list_results_by_sample(reports_connection(), sample_id)
    except tr_gw.GatewayError as exc:
        st.error(f"Could not load test reports: {exc}")
        return []


def result_count_for_transfer(transfer_id: int) -> int:
    """How many results anchor to a transfer (0 on service failure).

    A transfer referenced by a result is pinned against deletion
    (Test Reports Q11).
    """
    try:
        return tr_gw.count_results_by_transfer_id(
            reports_connection(), transfer_id
        )
    except tr_gw.GatewayError as exc:
        st.error(f"Could not load test-report links: {exc}")
        return 0
