"""Shared frontend helpers (page setup).

Every page calls `configure_page()` instead of the bare
`st.set_page_config(...)` boilerplate, so app-wide presentation tweaks
live in one place (AGENTS.md §4: keep styling minimal, one rule only).
"""
import streamlit as st

# Window (browser tab) title shown on every page (owner request): stays
# "Electronic Lab Notebook" regardless of the current page.
APP_TITLE = "Electronic Lab Notebook"

# Streamlit's default block-container padding leaves a large gap above and
# below page content; reduce it app-wide.
_TOP_PADDING_CSS = """
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 0.5rem;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
}
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
    st.markdown(_TOP_PADDING_CSS, unsafe_allow_html=True)
