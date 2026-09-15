"""Page-layer cross-service reads for the Ingredients page.

The Ingredients page reads how many formulas reference an ingredient —
the mirror of the Formulas page reading its batches reverse link
(frontend/formulas/dialogs.py ``batches_connection``). The query lives in
the Formulas service + gateway (a gateway routes to exactly one service);
this module only owns the connection.

Kept out of ``utils.py`` because it touches ``st.session_state``
(utils.py is pure, no streamlit).
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from backend.gateway import formulas as fgw


def formulas_connection() -> Any:
    """Shared in-process connection to the Formulas service.

    One connection per session, opened lazily. The dev-DB path is
    resolved at call time (not imported as a constant) so AppTest's
    per-test monkeypatched path is honoured.
    """
    from backend.services.formulas import store as formulas_store

    if "ingredients_formulas_conn" not in st.session_state:
        st.session_state.ingredients_formulas_conn = fgw.connect(
            formulas_store.DEV_DB_PATH
        )
    return st.session_state.ingredients_formulas_conn


def formula_counts_by_ingredient() -> dict[int, int]:
    """{ingredient_id: formula count}; empty map on service failure.

    The details metric and the delete guard share this one snapshot.
    """
    try:
        return fgw.count_formulas_by_ingredient_id(formulas_connection())
    except fgw.GatewayError as exc:
        st.error(f"Could not load formulas using ingredients: {exc}")
        return {}
