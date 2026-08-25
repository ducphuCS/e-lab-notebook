"""Shared frontend helpers (page setup).

Every page calls `configure_page()` instead of the bare
`st.set_page_config(...)` boilerplate, so app-wide presentation tweaks
live in one place (AGENTS.md §4: keep styling minimal, one rule only).
"""
import streamlit as st

# Streamlit's default block-container padding leaves a large gap above and
# below page content; reduce it app-wide.
_TOP_PADDING_CSS = """
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 0rem;
    padding-left: 5rem;
    padding-right: 5rem;
}
</style>
"""


def configure_page(page_title: str) -> None:
    """Set page config and apply the shared top-padding tweak."""
    st.set_page_config(page_title=page_title, layout="wide")
    st.markdown(_TOP_PADDING_CSS, unsafe_allow_html=True)
