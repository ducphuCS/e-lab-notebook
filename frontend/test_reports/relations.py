"""Page-layer cross-service reads for the Test Reports pages.

Test Reports attaches results to **samples and transfers**, so it reads
the Samples service to resolve sample codes, origin labels and a sample's
transfers — the mirror of the Samples page reading its Batches reverse
link (frontend/samples/relations.py). The query lives in the Samples
service + gateway (a gateway routes to exactly one service); this module
only owns the connection.

Kept out of ``utils.py`` because it touches ``st.session_state``
(utils.py is pure, no streamlit).
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from backend.gateway import samples as s_gw


def samples_connection() -> Any:
    """Shared in-process connection to the Samples service.

    One connection per session, opened lazily. The dev-DB path is
    resolved at call time (not imported as a constant) so AppTest's
    per-test monkeypatched path is honoured.
    """
    from backend.services.samples import store as samples_store

    if "test_reports_samples_conn" not in st.session_state:
        st.session_state.test_reports_samples_conn = s_gw.connect(
            samples_store.DEV_DB_PATH
        )
    return st.session_state.test_reports_samples_conn


def sample_index() -> dict[int, dict]:
    """{sample_id: sample record} for labels and the result dialog.

    Empty map on service failure.
    """
    try:
        records = s_gw.list_samples(samples_connection())
    except s_gw.GatewayError as exc:
        st.error(f"Could not load samples: {exc}")
        return {}
    return {int(record["id"]): record for record in records}


def transfers_for_sample(sample_id: int) -> list[dict]:
    """A sample's transfers (retention + dispatches), newest first."""
    try:
        return s_gw.list_transfers(samples_connection(), sample_id)
    except s_gw.GatewayError as exc:
        st.error(f"Could not load sample transfers: {exc}")
        return []


def transfer_index(sample_ids: list[int]) -> dict[int, dict]:
    """{transfer_id: transfer} across a set of samples (Results tab)."""
    index: dict[int, dict] = {}
    for sample_id in set(sample_ids or []):
        for transfer in transfers_for_sample(sample_id):
            index[int(transfer["id"])] = transfer
    return index
