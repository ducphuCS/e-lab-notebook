"""AppTest behavior tests for the Formulator Plan Mode page.

Layer: app behavior (docs/TEST_STRATEGIES.md §4.4) — runs the page
headlessly via streamlit.testing.v1.AppTest: no browser, no network.
"""
import pandas as pd
from streamlit.testing.v1 import AppTest


def _page() -> AppTest:
    return AppTest.from_file("frontend/formulator_plan_mode/app.py")


def test_page_loads_without_error() -> None:
    at = _page()
    at.run()
    assert not at.exception
    assert at.title[0].value == "Formulator Plan Mode"


def test_save_with_invalid_formulations_shows_error() -> None:
    # Pre-seed session state so the editor shows invalid data (missing
    # required item_code) and the page validator must reject the save.
    at = _page()
    bad = pd.DataFrame({"index": ["1"], "item_code": [""], "m_0": [1.0]})
    at.session_state["formulations_df"] = bad
    at.run()

    at.button[0].click().run()

    assert not at.exception
    assert any("Cannot save" in e.value for e in at.error)


def test_save_with_valid_data_shows_success() -> None:
    at = _page()
    good = pd.DataFrame({"index": ["1"], "item_code": ["A-1"], "m_0": [1.0]})
    at.session_state["formulations_df"] = good
    at.run()

    at.button[0].click().run()

    assert not at.exception
    assert any("Experiment drafted successfully" in e.value for e in at.success)
