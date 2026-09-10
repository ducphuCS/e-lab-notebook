"""Batches detail page (hidden child page, README Q7).

Reads the batch id from the query params (?batch_id=3), falling back to
session_state so AppTest can drive it headlessly. Renders the four tabs
from README §4: Overview, Composition, Processing, Samples. Reached via
st.switch_page from the overview.

The actuals are recorded *as it happens* here (README §3): status + actual
yield + observations on the Overview tab, per-ingredient actual amounts on
the Composition tab. Partial actual updates are merged sub-key wise by the
gateway, so the two editor surfaces never clobber each other.
"""
import streamlit as st

from backend.gateway import batches as gw
from backend.services.batches.schema import BATCH_STATUSES
from backend.services.batches.store import DEV_DB_PATH

from frontend.batches.dialogs import delete_dialog, edit_dialog
from frontend.common import configure_page, notify, show_pending_notification
from frontend.batches.utils import (
    COMPOSITION_EDITOR_COLUMNS,
    actual_rows,
    actual_yield,
    actual_from_editor,
    batch_stats,
    composition_editor_df,
    observations,
    planned_rows,
    processing_df,
    target_yield,
    yield_text,
)

configure_page()

# ------------------------------------------------------------------ data
if "batches_conn" not in st.session_state:
    st.session_state.batches_conn = gw.connect(DEV_DB_PATH)
conn = st.session_state.batches_conn

back_col, _ = st.columns([5, 1], vertical_alignment="center")
with back_col:
    if st.button("← Back to overview", key="back_overview"):
        # switch_page clears query params on navigation (batch_id included).
        st.switch_page("batches/app.py")

raw_id = st.query_params.get("batch_id")
if raw_id is None:
    raw_id = st.session_state.get("batches_detail_id")
try:
    batch_id = int(raw_id) if raw_id else None
except (TypeError, ValueError):
    batch_id = None

if batch_id is None:
    st.info("No batch selected — go back to the overview and open one.")
    st.stop()

record = gw.get_batch(conn, batch_id)
if record is None:
    st.warning("This batch no longer exists.")
    st.stop()

# ----------------------------------------------------------------- header
title_col, actions_col = st.columns([5, 1], vertical_alignment="center")
with title_col:
    st.title(record["name"])
    st.caption(
        f"{record['batch_code']} · made from {record['formula_name']} "
        f"v{record['formula_version']} · status: {record['status']}"
    )
with actions_col:
    if st.button(
        "✏️ Edit", type="primary", use_container_width=True, key="edit_detail"
    ):
        edit_dialog(conn, record)
    if st.button("🗑️ Delete", use_container_width=True, key="delete_detail"):
        delete_dialog(conn, record)

# ------------------------------------------------------------------- tabs
tab_overview, tab_composition, tab_processing, tab_samples = st.tabs(
    ["Overview", "Composition", "Processing", "Samples"]
)


def _render_overview(record: dict) -> None:
    """Header facts + the record-as-it-happens surface: status, actual
    yield, observations (README §3). Saves a partial actual update — the
    gateway merges it over the stored actual, so composition actuals are
    preserved."""
    g1a, g1b, g1c = st.columns(3)
    g1a.metric("Target yield", yield_text(target_yield(record)))
    g1b.metric("Formula", f"{record['formula_name']} v{record['formula_version']}")
    g1c.metric("Status", record["status"])

    g2a, g2b, g2c = st.columns(3)
    g2a.metric("Batch code", record["batch_code"])
    g2b.metric("Created", (record["created_at"] or "")[:10])
    g2c.metric("Updated", (record["updated_at"] or "")[:10])

    formula_col, _ = st.columns([2, 3])
    with formula_col:
        if st.button("Open formula in Library", key="open_formula"):
            st.switch_page(
                "formulas/detail.py",
                query_params={"formula_id": str(record["formula_id"])},
            )

    st.divider()
    st.write("**Record the run**")
    with st.form("record_overview"):
        status_index = (
            BATCH_STATUSES.index(record["status"])
            if record["status"] in BATCH_STATUSES
            else 0
        )
        status = st.selectbox(
            "Status", BATCH_STATUSES, index=status_index, key=f"ov_status_{record['id']}"
        )
        y1, y2 = st.columns(2)
        y_actual = actual_yield(record)
        amount = y1.number_input(
            "Actual yield — amount",
            min_value=0.0,
            value=float(y_actual["amount"]) if y_actual and y_actual.get("amount") is not None else None,
            key=f"ov_yield_{record['id']}",
        )
        uom = y2.text_input(
            "Actual yield — unit",
            value=(y_actual or {}).get("uom") or "",
            key=f"ov_yield_uom_{record['id']}",
        )
        obs = st.text_area(
            "Observations",
            value=observations(record),
            key=f"ov_obs_{record['id']}",
        )
        if st.form_submit_button("Save run details", type="primary"):
            actual_patch: dict = {"observations": obs}
            if amount is not None:
                actual_patch["yield"] = {"amount": amount, "uom": uom.strip()}
            try:
                gw.update_batch(
                    conn,
                    record["id"],
                    {"status": status, "actual": actual_patch},
                )
            except gw.GatewayError as exc:
                problems = exc.problems or [str(exc)]
                notify(
                    False,
                    "Could not save run details — " + "; ".join(problems),
                )
            else:
                # Rerun refreshes the header metrics; the queued outcome is
                # rendered at the end of that rerun.
                notify(True, "Run details saved.")
                st.rerun()

    if record.get("owner"):
        st.caption(f"Owner: {record['owner']}")


def _render_composition(record: dict) -> None:
    """Planned vs actual per ingredient (README §4 Composition tab)."""
    if not planned_rows(record):
        st.info("This batch has no planned composition.")
        return

    st.caption(
        "Planned amounts were fixed at creation: derived from this "
        f"formula's composition ({record['formula_name']} "
        f"v{record['formula_version']}), scaled to the batch's target "
        "yield. Later formula edits do not change this batch."
    )

    st.write("**Actual amounts per ingredient**")
    st.caption(
        "Enter what was actually weighed/used. Deviation (actual − "
        "planned) is derived and shown only when the units match "
        "(README §5.1)."
    )
    editor = st.data_editor(
        composition_editor_df(record),
        hide_index=True,
        width="stretch",
        # Only the visible columns are displayed; ingredient_id /
        # ingredient_name stay in the data (read-only) so actual rows can
        # be rebuilt with their identity (README §5.1).
        column_order=COMPOSITION_EDITOR_COLUMNS,
        column_config={
            "no": st.column_config.NumberColumn("No", disabled=True),
            "ingredient": st.column_config.TextColumn(
                "Ingredient", disabled=True
            ),
            "planned": st.column_config.NumberColumn(
                "Planned", disabled=True, format="%.2f"
            ),
            "plan_uom": st.column_config.TextColumn("Unit", disabled=True),
            "actual": st.column_config.NumberColumn(
                "Actual", min_value=0.0, format="%.2f"
            ),
            "actual_uom": st.column_config.TextColumn("Actual unit"),
            "deviation": st.column_config.NumberColumn(
                "Deviation", disabled=True, format="%.2f"
            ),
            "note": st.column_config.TextColumn("Note"),
        },
        key=f"composition_editor_{record['id']}",
    )
    if st.button("Save actual amounts", type="primary", key=f"save_actual_{record['id']}"):
        rows = actual_from_editor(editor)
        try:
            # Sub-key merge in the gateway preserves yield/observations.
            gw.update_batch(conn, record["id"], {"actual": {"composition": rows}})
        except gw.GatewayError as exc:
            problems = exc.problems or [str(exc)]
            notify(
                False,
                "Could not save actual amounts — " + "; ".join(problems),
            )
        else:
            # Rerun refreshes the editor and its derived deviations from
            # the stored rows; the queued outcome is rendered at the end of
            # that rerun (see show_pending_notification).
            notify(True, "Actual amounts saved.")
            st.rerun()
    if actual_rows(record):
        st.caption(f"{len(actual_rows(record))} of {len(planned_rows(record))} ingredient(s) recorded.")


def _render_processing(record: dict) -> None:
    """Planned processing parameters, read-only (README Q4/Q8)."""
    df = processing_df(record)
    if df.empty:
        st.info(
            "No processing plan — the formula has no procedure steps. "
            "Actual processing values are not recorded in v0 (README Q8)."
        )
        return
    st.write("**Planned processing values**")
    st.caption(
        "From the formula's procedure snapshot — read-only. Actual "
        "processing values arrive with the step-by-step execution log "
        "later (README Q2/Q8); none are recorded in v0."
    )
    st.dataframe(df.fillna("—"), hide_index=True, width="stretch")


def _render_samples(record: dict) -> None:
    """Samples + their test reports (placeholders until Samples lands)."""
    stats = batch_stats(record)
    s1, s2 = st.columns(2)
    s1.metric("Samples", stats["samples"])
    s2.metric("Test reports", stats["reports"])
    st.caption(
        "Samples taken from this batch — and their test reports — will be "
        "listed here once the Samples module lands (README §6)."
    )


# ---------------------------------------------------------------- sections
with tab_overview:
    _render_overview(record)
with tab_composition:
    _render_composition(record)
with tab_processing:
    _render_processing(record)
with tab_samples:
    _render_samples(record)

# A write outcome (actual amounts / run details / edit or delete dialog) may
# be pending in session_state — render it. Only one dialog can be open per
# run; no other dialog is open here.
show_pending_notification()
