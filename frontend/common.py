"""Shared frontend helpers (page setup).

Every page calls `configure_page()` instead of the bare
`st.set_page_config(...)` boilerplate, so app-wide presentation tweaks
live in one place (AGENTS.md §4: keep styling minimal, one rule only).
"""
import streamlit as st

# Window (browser tab) title shown on every page (owner request): stays
# "Electronic Lab Notebook" regardless of the current page.
APP_TITLE = "Electronic Lab Notebook"

# Shared, minimal page CSS (AGENTS.md §4: default look, one rule at a
# time):
# - Streamlit's default block-container padding leaves a large gap above
#   and below page content; reduce it app-wide.
# - st.metric values render at a large font by default, so longer values
#   (e.g. a formula name + version, a batch code row) truncate. Use the
#   smaller size Ingredients already applied to its Details panel (owner
#   request); metric labels keep the default size.
_SHARED_CSS = """
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 0.5rem;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
}
[data-testid="stMetricValue"] { font-size: 1.1rem; }
</style>
"""


def configure_page() -> None:
    """Set page config (constant window title) and apply the shared CSS tweaks.

    The Streamlit header is kept native (not hidden via CSS): the sidebar's
    reopen button (`stExpandSidebarButton`) lives inside it and must stay
    reachable after the sidebar is collapsed. Instead, `client.toolbarMode`
    is set to "minimal" — the built-in, scriptable option that strips the
    menu / deploy clutter from the header.
    """
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.set_option("client.toolbarMode", "minimal")
    st.markdown(_SHARED_CSS, unsafe_allow_html=True)


# --- write-outcome notifications -----------------------------------------
# One shared way to report the outcome of a write (create/update/delete/
# duplicate) that is followed by a rerun or navigation. Inline banners and
# plain toasts do not survive that rerun in the Streamlit 1.60 frontend, so
# the outcome is stashed in session state and rendered on the next page run
# (AGENTS.md §4: one shared helper, no per-module copies):
#   * success -> short, non-blocking st.toast
#   * failure -> small modal "Save result" that stays until dismissed and
#     can carry the backend's validation problems
# Read-only render state (load errors, empty lists) and validation errors
# shown while an editor/dialog is still open stay inline at their call
# sites — no rerun happens there, so native st.info/warning/error already
# persist next to the user's input.
NOTIFICATION_KEY = "app_notification"  # {"ok": bool, "msg": str}


def notify(ok: bool, msg: str) -> None:
    """Queue a write outcome for the page run that follows (see note above)."""
    st.session_state[NOTIFICATION_KEY] = {"ok": ok, "msg": msg}


def _clear_notification() -> None:
    """on_dismiss: X / ESC / click-outside drops the pending failure."""
    st.session_state.pop(NOTIFICATION_KEY, None)


@st.dialog(
    "Save result",
    width="small",
    dismissible=True,
    on_dismiss=_clear_notification,
)
def _result_dialog() -> None:
    """Small modal reporting a failed write with its validation problems."""
    result = st.session_state.get(NOTIFICATION_KEY)
    if not result:
        # Dismissed on a rerun before this ran — close right away.
        st.rerun()
        return
    st.error(result["msg"], icon=":material/error:")
    if st.button("OK", type="primary", use_container_width=True):
        _clear_notification()
        st.rerun()


def show_pending_notification() -> None:
    """Render a queued write outcome. Call once at the end of every page run.

    Success shows a one-shot toast and is consumed; failure opens the
    result modal, which clears the outcome on dismiss. Do not call this
    while another dialog is open in the same run (only one dialog per run).
    """
    result = st.session_state.get(NOTIFICATION_KEY)
    if result is None:
        return
    if result["ok"]:
        st.session_state.pop(NOTIFICATION_KEY, None)
        st.toast(result["msg"], icon=":material/check_circle:")
    else:
        _result_dialog()
