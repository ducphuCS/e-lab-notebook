"""ELN v2 frontend entrypoint — page router.

Launched by `main.py`, or directly with:
`uv run streamlit run frontend/app.py`
(I like this, keep it untouched - ducphu)

Registers every page of the app. The four planned modules are placeholder
stubs for now; replace each stub with a real page (e.g.
`st.Page("library/app.py", ...)`) as the module's folder lands.
"""
import streamlit as st

from frontend.common import configure_page


def main() -> None:
    configure_page()

    # Sections are defined via a mapping: each key is the section header,
    # each value the list of pages in that section.
    pages = {
        "Overview": [
            st.Page(
                "dashboard/app.py",
                title="Dashboard",
                icon=":material/dashboard:",
                url_path="dashboard",
                default=True,
            ),
            st.Page(
                "projects/app.py",
                title="Projects",
                icon=":material/folder:",
                url_path="projects",
            ),
        ],
        "Library": [
            st.Page(
                "ingredients/app.py",
                title="Ingredients",
                icon=":material/inventory_2:",
                url_path="ingredients",
            ),
            st.Page(
                "equipment/app.py",
                title="Equipment",
                icon=":material/biotech:",
                url_path="equipment",
            ),
            st.Page(
                "test_methods/app.py",
                title="Test Methods",
                icon=":material/menu_book:",
                url_path="test-methods",
            ),
            st.Page(
                "test_panels/app.py",
                title="Test Panels",
                icon=":material/view_agenda:",
                url_path="test-panels",
            ),
            st.Page(
                "formulas/app.py",
                title="Formulas",
                icon=":material/functions:",
                url_path="formulas",
            ),
            st.Page(
                "formulas/detail.py",
                title="Formula Detail",
                icon=":material/tab:",
                # st.navigation in streamlit 1.60 does not support nested
                # url_paths ("foo/bar"); the detail page gets its own
                # single-segment path and the formula id travels in
                # st.query_params (?formula_id=3) (README Q5).
                url_path="formula-detail",
                visibility="hidden",
            ),
            st.Page(
                "documents/app.py",
                title="Documents",
                icon=":material/article:",
                url_path="documents",
            ),
        ],
        "Lab": [
            st.Page(
                "batches/app.py",
                title="Batches",
                icon=":material/layers:",
                url_path="batches",
            ),
            st.Page(
                "samples/app.py",
                title="Samples",
                icon=":material/science:",
                url_path="samples",
            ),
            st.Page(
                "test_reports/app.py",
                title="Test Reports",
                icon=":material/assessment:",
                url_path="test-reports",
            ),
        ],
        "Analyze": [
            st.Page(
                "doe/app.py",
                title="DOE",
                icon=":material/analytics:",
                url_path="doe",
            ),
        ],
    }

    st.navigation(pages).run()


if __name__ == "__main__":
    main()
