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
