"""Formulas detail page (hidden child page, README Q5).

Reads the formula id from the query params (?formula_id=3), falling back
to session_state so AppTest can drive it headlessly. Renders the six tabs
from README §4: Overview, Composition, Params, Procedure, Documents,
Versions. Reached via st.switch_page from the overview.
"""
import pandas as pd
import streamlit as st

from backend.gateway import formulas as gw
from backend.services.formulas.store import DEV_DB_PATH

from frontend.common import configure_page
from frontend.formulas.dialogs import form_dialog
from frontend.formulas.utils import (
    composition_to_df,
    custom_fields_to_df,
    derive_percentages,
    diff_compositions,
    formula_stats,
    params_to_df,
    procedure_to_df,
)

configure_page()

# ------------------------------------------------------------------ data
if "formulas_conn" not in st.session_state:
    st.session_state.formulas_conn = gw.connect(DEV_DB_PATH)
conn = st.session_state.formulas_conn

back_col, _ = st.columns([5, 1], vertical_alignment="center")
with back_col:
    if st.button("← Back to overview", key="back_overview"):
        # switch_page clears query params on navigation (formula_id included).
        st.switch_page("formulas/app.py")

raw_id = st.query_params.get("formula_id")
if raw_id is None:
    raw_id = st.session_state.get("formulas_detail_id")
try:
    formula_id = int(raw_id) if raw_id else None
except (TypeError, ValueError):
    formula_id = None

if formula_id is None:
    st.info("No formula selected — go back to the overview and open one.")
    st.stop()

record = gw.get_formula(conn, formula_id)
if record is None:
    st.warning("This formula no longer exists.")
    st.stop()

# ----------------------------------------------------------------- header
title_col, actions_col = st.columns([5, 1], vertical_alignment="center")
with title_col:
    st.title(record["name"])
    st.caption(
        f"ID {record['id']} · Version: {record['version']} · Status: {record['status']}"
    )
with actions_col:
    if st.button(
        "✏️ Edit", type="primary", use_container_width=True, key="edit_detail"
    ):
        form_dialog(conn, record)

# ------------------------------------------------------------------- tabs
tab_overview, tab_composition, tab_params, tab_procedure, tab_documents, tab_versions = (
    st.tabs(["Overview", "Composition", "Params", "Procedure", "Documents", "Versions"])
)

# ---------------------------------------------------------------- sections
def _render_overview(record: dict) -> None:
    g1a, g1b, g1c = st.columns(3)
    g1a.metric("Project", record["project"] or "—")
    g1b.metric("Family", record["family"] or "—")
    g1c.metric("Owner", record["owner"] or "—")

    g2a, g2b, g2c = st.columns(3)
    g2a.metric("Status", record["status"])
    g2b.metric("Version", record["version"])
    g2c.metric("Updated", (record["updated_at"] or "")[:10])

    stats = formula_stats(record)
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Ingredients", stats["ingredients"])
    s2.metric("Steps", stats["steps"])
    s3.metric("Batches", stats["batches"])
    s4.metric("Samples", stats["samples"])

    if record.get("description"):
        st.markdown(f"**Description**\n\n{record['description']}")
    if record.get("tags"):
        st.markdown("**Tags** — " + ", ".join(record["tags"]))
    st.caption(f"Created {record['created_at'] or '—'}")

    custom_df = custom_fields_to_df(record.get("custom_fields"))
    if not custom_df.empty:
        st.write("**Custom fields**")
        st.dataframe(custom_df, hide_index=True, width="stretch")

    st.divider()
    st.write("**Related records**")
    st.caption(
        "Batches, samples and test reports produced from this formula — "
        "placeholders until the Lab module lands (README §6)."
    )
    r1, r2, r3 = st.columns(3)
    r1.metric("Batches", stats["batches"])
    r2.metric("Samples", stats["samples"])
    r3.metric("Test reports", 0)


def _render_composition(record: dict) -> None:
    composition = record.get("composition") or []
    if not composition:
        st.info("This formula has no composition yet.")
        return
    percentages = derive_percentages(composition)
    rows = []
    for i, item in enumerate(composition):
        rows.append(
            {
                "no": item.get("no"),
                "ingredient": item.get("ingredient_name"),
                "role": item.get("role") or "—",
                "amount": item.get("amount"),
                "uom": item.get("uom") or "—",
                "%": f"{percentages[i]:.1f}" if percentages is not None else "—",
                # Ingredient unit cost lands with Formulas (README Q8).
                "cost": "—",
                "notes": item.get("notes") or "—",
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if percentages is None:
        st.caption(
            "Percentage is not computable — rows use different UOMs "
            "(README Q10)."
        )


def _render_params(record: dict) -> None:
    params = record.get("params") or []
    if not params:
        st.info("No theoretical params defined.")
        return
    rows = [
        {
            "parameter": p.get("parameter"),
            "source": p.get("source") or "—",
            "aggregation": p.get("aggregation") or "—",
            "value": p.get("value") or "—",
        }
        for p in params
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(
        "Value is entered manually in v0; evaluation from ingredient custom "
        "fields is a later phase (README Q3)."
    )


def _render_procedure(record: dict) -> None:
    procedure = record.get("procedure") or []
    if not procedure:
        st.info("No procedure defined.")
        return
    rows = []
    for step in procedure:
        ingredients = ", ".join(
            item.get("ingredient_name", "")
            for item in step.get("ingredients") or []
            if item.get("ingredient_name")
        )
        params = "; ".join(
            f"{key}={value}" for key, value in (step.get("params") or {}).items()
        )
        rows.append(
            {
                "step": step.get("name"),
                "ingredients": ingredients or "—",
                "equipment": step.get("equipment") or "—",
                "duration": step.get("duration") or "—",
                "params": params or "—",
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _render_documents(record: dict) -> None:
    st.info("The Documents page owns attachments (README Q6).")
    st.caption(
        "Documents linked to this formula will be listed here once the "
        "Documents module lands. None linked yet."
    )


def _highlight_changed(changed: set[int]):
    def apply(row) -> list[str]:
        no = row["no"]
        return ["background-color: #fde68a" if no in changed else "" for _ in row]

    return apply


def _styled(df: pd.DataFrame, changed: set[int]):
    return df.style.apply(_highlight_changed(changed), axis=1)


def _render_versions(conn, formula_id: int) -> None:
    versions = gw.list_formula_versions(conn, formula_id)
    if not versions:
        st.info("No versions recorded.")
        return
    st.caption(
        f"This formula has {len(versions)} version(s). A new version is "
        "created only when the composition changes (README Q2)."
    )
    if len(versions) < 2:
        st.caption(
            "Edit the composition to create a second version, then compare "
            "them side by side here."
        )
        return

    labels = [
        f"v{v['version']} · {(v['created_at'] or '')[:10]}" for v in versions
    ]
    c1, c2 = st.columns(2)
    idx_a = c1.selectbox(
        "Version A",
        range(len(versions)),
        index=len(versions) - 2,
        format_func=lambda i: labels[i],
        key="version_a",
    )
    idx_b = c2.selectbox(
        "Version B",
        range(len(versions)),
        index=len(versions) - 1,
        format_func=lambda i: labels[i],
        key="version_b",
    )

    old = versions[idx_a]["snapshot"].get("composition") or []
    new = versions[idx_b]["snapshot"].get("composition") or []
    diff = diff_compositions(old, new)

    if not diff["changed"]:
        st.success("No composition differences between these versions.")
        return

    changed_set = set(diff["changed"])
    left, right = st.columns(2)
    with left:
        st.markdown(f"**{labels[idx_a]}**")
        st.dataframe(
            _styled(composition_to_df(diff["old"]), changed_set),
            hide_index=True,
            width="stretch",
        )
    with right:
        st.markdown(f"**{labels[idx_b]}**")
        st.dataframe(
            _styled(composition_to_df(diff["new"]), changed_set),
            hide_index=True,
            width="stretch",
        )
    st.caption("Highlighted rows differ between the versions.")


# ------------------------------------------------------------------- tabs
with tab_overview:
    _render_overview(record)
with tab_composition:
    _render_composition(record)
with tab_params:
    _render_params(record)
with tab_procedure:
    _render_procedure(record)
with tab_documents:
    _render_documents(record)
with tab_versions:
    _render_versions(conn, formula_id)
