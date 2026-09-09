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
