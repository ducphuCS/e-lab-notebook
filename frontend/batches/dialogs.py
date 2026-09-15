"""Shared dialogs for the Batches pages (overview and detail).

st.dialog modals per README §4 — one implementation, launched from both
entry points. Pages stay thin glue (docs/TEST_STRATEGIES.md §5): the
dialogs call the gateway directly and reuse the pure helpers in utils.py.

The create dialog reads the Formulas service (in-process connection) to
pick the formula the batch is made from — the same pattern Formulas'
composition editor uses to read the Ingredients master.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from backend.gateway import batches as gw
from backend.gateway import formulas as fgw
from backend.services.batches.schema import BATCH_STATUSES
from backend.services.formulas.store import DEV_DB_PATH as FORMULAS_DB_PATH

from frontend.batches.relations import samples_for_batch
from frontend.batches.utils import (
    BATCHES_TABLE_KEY,
    build_planned,
    formula_options,
    normalize_plan_rows,
    plan_editor_df,
    plan_from_editor_df,
    planned_rows,
    samples_block_reason,
    yield_text,
)

from frontend.common import notify


def _load_formulas() -> list[dict]:
    """Formula master records for the create dialog's formula picker."""
    if "batches_formulas_conn" not in st.session_state:
        st.session_state.batches_formulas_conn = fgw.connect(FORMULAS_DB_PATH)
    conn = st.session_state.batches_formulas_conn
    try:
        return fgw.list_formulas(conn)
    except fgw.GatewayError as exc:
        st.error(f"Could not load formulas: {exc}")
        return []


@st.dialog("New batch", width="medium")
def create_dialog(conn: Any) -> None:
    """Create a batch from a formula (README Q1/Q3/Q4).

    The user picks the formula and an optional target yield; the planned
    snapshot (scaled composition + processing params) is previewed
    read-only before saving. A batch is always born as a *planned* plan.
    """
    st.markdown("### New batch")
    formulas = _load_formulas()
    options, label_to_id = formula_options(formulas)

    if not options:
        st.warning(
            "No formulas yet — create one on the Formulas page first, so "
            "there is something to make a batch from."
        )
        st.stop()

    name = st.text_input("Name *", placeholder="e.g. Emulsion X — 2500 g run")
    formula_label = st.selectbox("Formula *", options)
    owner = st.text_input("Owner", value="")

    st.write("**Target yield (optional)**")
    tc1, tc2 = st.columns(2)
    target_amount = tc1.number_input(
        "Amount", min_value=0.0, value=None, placeholder="e.g. 2500",
        help="Planned amounts scale to this target (same-unit composition).",
    )
    target_uom = tc2.text_input("Unit", placeholder="e.g. g")

    formula_id = label_to_id.get(formula_label)
    formula = next(
        (f for f in formulas if f["id"] == formula_id), None
    ) if formula_id else None

    if formula is None:
        st.error("Could not load the selected formula.")
        st.stop()

    rows = normalize_plan_rows(formula.get("composition"))
    if not rows:
        st.warning(
            f"**{formula['name']}** has no composition rows yet — add "
            "ingredients on the Formulas page first. Nothing to plan a "
            "batch from."
        )
        st.stop()

    # Live preview of the planned snapshot (target given -> scaled rows).
    planned = build_planned(formula, target_amount, target_uom)

    if planned.get("target_yield"):
        st.caption(
            f"Planned amounts scaled to a target of {yield_text(planned['target_yield'])}."
        )
    else:
        st.caption(
            "Planned amounts copied from the formula as-is (no target, or "
            "composition rows use different units — README §5.1)."
        )

    preview_df = pd.DataFrame(
        [
            {
                "no": row.get("no"),
                "ingredient": row.get("ingredient_name"),
                "amount": row.get("amount"),
                "uom": row.get("uom") or "—",
            }
            for row in planned.get("composition") or []
        ],
        columns=("no", "ingredient", "amount", "uom"),
    )
    st.dataframe(preview_df, hide_index=True, width="stretch")

    st.caption(f"Status: **planned** · Formula: **{formula['name']}** (v{formula.get('version')})")

    c1, c2 = st.columns(2)
    if c1.button("Create batch", type="primary"):
        payload = {
            "name": name.strip(),
            "formula_id": formula["id"],
            "formula_name": formula["name"],
            "formula_version": formula.get("version") or 1,
            "status": "planned",
            "owner": owner.strip() or None,
            "planned": planned,
            "actual": {},
        }
        try:
            gw.create_batch(conn, payload)
        except gw.GatewayError as exc:
            problems = exc.problems or [str(exc)]
            st.error("Could not create batch:\n- " + "\n- ".join(problems))
        else:
            # The dialog closes on the rerun; the queued outcome is
            # rendered on the page that follows.
            notify(True, "Batch created.")
            st.rerun()
    if c2.button("Cancel", key="cancel_create"):
        st.rerun()


@st.dialog("Edit batch", width="medium")
def edit_dialog(conn: Any, record: dict) -> None:
    """Edit a batch's header fields (name, owner, status) — always.

    While the batch is still *planned*, the plan rows (amount/uom/notes)
    are also editable (README decision 2026-09-03); once the batch has
    left 'planned' the plan is frozen (Q1) and only the header shows.
    """
    is_planned = record["status"] == "planned"
    st.markdown(f"### Edit {record['batch_code']} — {record['name']}")

    name = st.text_input("Name *", value=record.get("name", ""))
    owner = st.text_input("Owner", value=record.get("owner") or "")
    status_index = BATCH_STATUSES.index(record["status"]) \
        if record["status"] in BATCH_STATUSES else 0
    status = st.selectbox("Status", BATCH_STATUSES, index=status_index)

    original_rows: list[dict] = []
    if is_planned:
        st.write("**Plan**")
        st.caption(
            f"Amounts copied from {record['formula_name']} "
            f"v{record['formula_version']}. Editable while the batch is "
            "still planned."
        )
        editor = st.data_editor(
            plan_editor_df(record),
            hide_index=True,
            width="stretch",
            column_config={
                "no": st.column_config.NumberColumn("No", disabled=True),
                "ingredient": st.column_config.TextColumn(
                    "Ingredient", disabled=True
                ),
                "amount": st.column_config.NumberColumn(
                    "Amount", min_value=0.0, format="%.2f"
                ),
                "uom": st.column_config.TextColumn("UOM"),
                "notes": st.column_config.TextColumn("Notes"),
            },
            key=f"plan_editor_{record['id']}",
            num_rows="fixed",
        )
        # The (possibly edited) plan is rebuilt on save from the editor;
        # plan_from_editor_df keeps the original ingredient identity.
        original_rows = planned_rows(record)

    c1, c2 = st.columns(2)
    if c1.button("Save", type="primary"):
        payload: dict = {
            "name": name.strip(),
            "owner": owner.strip() or None,
            "status": status,
        }
        if is_planned:
            payload["planned"] = {
                **(record.get("planned") or {}),
                "composition": plan_from_editor_df(editor, original_rows),
            }
        try:
            gw.update_batch(conn, record["id"], payload)
        except gw.GatewayError as exc:
            problems = exc.problems or [str(exc)]
            st.error("Could not save batch:\n- " + "\n- ".join(problems))
        else:
            notify(True, "Batch updated.")
            st.rerun()
    if c2.button("Cancel", key="cancel_edit"):
        st.rerun()


@st.dialog("Delete batch")
def delete_dialog(conn: Any, record: dict) -> None:
    """Delete confirmation (README Q6).

    Deletion is allowed only while the batch is *planned* and has no
    linked samples (test reports join the guard when that module lands).
    The samples check reads the Samples service reverse link, mirroring
    the Formulas delete guard reading its batches.
    """
    if record["status"] != "planned":
        st.warning(
            f"**{record['batch_code']}** cannot be deleted: it is "
            f"'{record['status']}', not 'planned'. Only planned batches "
            "with no samples or test reports can be deleted (README Q6)."
        )
        if st.button("Close", key="cancel_delete_blocked"):
            st.rerun()
        return

    reason = samples_block_reason(len(samples_for_batch(record["id"])))
    if reason:
        st.warning(
            f"**{record['batch_code']} — {record['name']}** cannot be "
            f"deleted — {reason} A batch that produced samples keeps its "
            "traceability (README Q6)."
        )
        if st.button("Close", key="cancel_delete_samples_blocked"):
            st.rerun()
        return

    st.warning(
        f"Delete **{record['batch_code']} — {record['name']}**? "
        "This cannot be undone."
    )
    c1, c2 = st.columns(2)
    if c1.button("Confirm delete", type="primary"):
        try:
            gw.delete_batch(conn, record["id"])
        except gw.GatewayError as exc:
            st.error(f"Delete failed: {exc}")
        else:
            notify(True, "Batch deleted.")
            # The deleted row was selected; drop the stale selection so the
            # overview table does not keep an out-of-bounds index on rerun.
            if BATCHES_TABLE_KEY in st.session_state:
                st.session_state[BATCHES_TABLE_KEY] = {"selection": {"rows": []}}
            st.switch_page("batches/app.py")
    if c2.button("Cancel", key="cancel_delete"):
        st.rerun()

