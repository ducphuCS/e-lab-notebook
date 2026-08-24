"""ELN v2 frontend entrypoint — page router.

Launched by `main.py`, or directly with:
`uv run streamlit run frontend/app.py`
(I like this, keep it untouched - ducphu)

Registers every page of the app. The four planned modules are placeholder
stubs for now; replace each stub with a real page (e.g.
`st.Page("library/app.py", ...)`) as the module's folder lands.
"""
from typing import Callable

import streamlit as st


def _module_stub(title: str, description: str) -> Callable[[], None]:
    """Return a placeholder page for a not-yet-built module."""

    def page() -> None:
        st.title(title)
        st.caption(description)
        st.info("This module is planned but not implemented yet.")

    return page


def main() -> None:
    st.set_page_config(page_title="ELN v2", layout="wide")

    pages = [
        # Planned modules (placeholders until their pages are built).
        st.Page(
            _module_stub("Overview", "Project timeline, risks, and individual workload."),
            title="Overview",
            icon=":material/dashboard:",
            url_path="overview",
            default=True,
        ),
        st.Page(
            _module_stub(
                "Library",
                "Ingredients, equipment, test methods, test panels, and formulas.",
            ),
            title="Library",
            icon=":material/library_books:",
            url_path="library",
        ),
        st.Page(
            _module_stub("Lab", "Actual lab work: batches, samples, and test reports."),
            title="Lab",
            icon=":material/science:",
            url_path="lab",
        ),
        st.Page(
            _module_stub("Analyze", "Learnings from DoE chains and design of new DoEs."),
            title="Analyze",
            icon=":material/analytics:",
            url_path="analyze",
        ),
        # Existing standalone page, now routed through the frontend entrypoint.
        st.Page(
            "formulator_plan_mode/app.py",
            title="Formulator Plan Mode",
            icon=":material/edit_note:",
            url_path="formulator-plan-mode",
        ),
    ]

    st.navigation(pages).run()


if __name__ == "__main__":
    main()
