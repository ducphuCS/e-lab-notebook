"""Unit tests for the shared write-outcome notification (frontend/common.py).

Layer: unit (docs/TEST_STRATEGIES.md §4). The queue lives in session state
and is rendered by Streamlit elements, so a tiny AppTest script drives it:
success must surface as a one-shot toast; failure must open the blocking
result modal with its validation problems.
"""
from streamlit.testing.v1 import AppTest

from frontend.common import NOTIFICATION_KEY


def _notification_script(ok: bool, msg: str) -> None:
    # AppTest.from_function runs the body in isolation, so it re-imports.
    from frontend.common import notify, show_pending_notification

    notify(ok, msg)
    show_pending_notification()


def test_success_renders_toast_and_is_consumed() -> None:
    at = AppTest.from_function(
        _notification_script, args=(True, "Saved.")
    ).run()
    assert not at.exception
    assert any(t.value == "Saved." for t in at.toast)
    # One-shot: the queue is cleared so a later rerun does not repeat it.
    assert NOTIFICATION_KEY not in at.session_state


def test_failure_opens_result_modal_with_problems() -> None:
    at = AppTest.from_function(
        _notification_script,
        args=(False, "Could not save — amount must be positive"),
    ).run()
    assert not at.exception
    assert any(
        "amount must be positive" in e.value for e in at.error
    )
    assert any(b.label == "OK" for b in at.button)
