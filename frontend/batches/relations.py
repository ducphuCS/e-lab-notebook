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
from backend.gateway import test_reports as tr_gw


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


# --- Test Reports reverse link (README §6 / Test Reports Q13) --------------

def reports_connection() -> Any:
    """Shared in-process connection to the Test Reports service.

    One connection per session, opened lazily; the dev-DB path is
    resolved at call time so AppTest's per-test monkeypatched path is
    honoured.
    """
    from backend.services.test_reports import store as reports_store

    if "batches_reports_conn" not in st.session_state:
        st.session_state.batches_reports_conn = tr_gw.connect(
            reports_store.DEV_DB_PATH
        )
    return st.session_state.batches_reports_conn


def report_count_for_samples(sample_ids: list[int]) -> int:
    """Distinct report count across a set of samples (0 on failure).

    A report covering several of the batch's samples is counted once.
    """
    try:
        return tr_gw.count_reports_by_sample_ids(
            reports_connection(), sample_ids
        )
    except tr_gw.GatewayError as exc:
        st.error(f"Could not load test-report counts: {exc}")
        return 0


def report_counts_by_batch() -> dict[int, int]:
    """{batch_id: distinct report count} for the overview stats.

    The batch->sample mapping comes from the Samples service; the report
    count is derived from those samples' results (Test Reports Q13).
    Empty map on service failure.
    """
    try:
        samples = sgw.list_samples(samples_connection())
    except sgw.GatewayError as exc:
        st.error(f"Could not load samples: {exc}")
        return {}
    sample_ids_by_batch: dict[int, list[int]] = {}
    for sample in samples:
        batch_id = sample.get("batch_id")
        if batch_id is not None:
            sample_ids_by_batch.setdefault(int(batch_id), []).append(
                int(sample["id"])
            )
    return {
        batch_id: report_count_for_samples(sample_ids)
        for batch_id, sample_ids in sample_ids_by_batch.items()
    }
