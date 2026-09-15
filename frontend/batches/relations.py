"""Page-layer cross-service reads for the Batches pages.

The Batches pages read the Samples service for their downstream link
(README §6): sample counts on the overview/detail and the delete guard
(a batch with samples cannot be deleted). The query lives in the Samples
service + gateway (a gateway routes to exactly one service); this module
only owns the connection.

Kept out of ``utils.py`` because it touches ``st.session_state``
(utils.py is pure, no streamlit).
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from backend.gateway import samples as sgw


def samples_connection() -> Any:
    """Shared in-process connection to the Samples service.

    One connection per session, opened lazily. The dev-DB path is
    resolved at call time (not imported as a constant) so AppTest's
    per-test monkeypatched path is honoured.
    """
    from backend.services.samples import store as samples_store

    if "batches_samples_conn" not in st.session_state:
        st.session_state.batches_samples_conn = sgw.connect(
            samples_store.DEV_DB_PATH
        )
    return st.session_state.batches_samples_conn


def sample_counts_by_batch() -> dict[int, int]:
    """{batch_id: sample count}; empty map on service failure.

    The overview stats and the delete guard share this one snapshot.
    """
    try:
        return sgw.count_samples_by_batch_id(samples_connection())
    except sgw.GatewayError as exc:
        st.error(f"Could not load samples: {exc}")
        return {}


def samples_for_batch(batch_id: int) -> list[dict]:
    """Light summaries of the samples taken from a batch (reverse link)."""
    try:
        return sgw.list_samples_by_batch(samples_connection(), batch_id)
    except sgw.GatewayError as exc:
        st.error(f"Could not load samples: {exc}")
        return []
