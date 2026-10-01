"""Contract tests for the test_reports gateway client.

Layer: contracts (docs/TEST_STRATEGIES.md §4.3). Asserts, against golden
JSON fixtures in tests/contracts/fixtures/test_reports/: *given this
service response, the gateway accepts it; given a malformed one, it
rejects it with a clear error.* No network — the response validators are
pure.
"""
import json
from pathlib import Path

import pytest

from backend.gateway import test_reports as gw

FIXTURES = Path(__file__).parent / "fixtures" / "test_reports"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


# --- reports ---------------------------------------------------------------

def test_valid_report_record_is_accepted() -> None:
    assert gw.validate_report_record(_fixture("valid_report")) == []


@pytest.mark.parametrize(
    "name",
    ["malformed_report_missing_fields", "malformed_report_bad_fields"],
)
def test_malformed_report_records_are_rejected(name: str) -> None:
    assert gw.validate_report_record(_fixture(name)) != []


def test_malformed_report_reports_the_missing_fields() -> None:
    problems = gw.validate_report_record(
        _fixture("malformed_report_missing_fields")
    )
    assert any("missing fields" in p for p in problems)


# --- results ---------------------------------------------------------------

def test_valid_result_record_is_accepted() -> None:
    assert gw.validate_result_record(_fixture("valid_result")) == []


def test_malformed_result_record_is_rejected() -> None:
    assert gw.validate_result_record(_fixture("malformed_result")) != []


def test_valid_result_summary_is_accepted() -> None:
    assert gw.validate_result_summary(_fixture("valid_result_summary")) == []


def test_result_summary_reports_the_missing_fields() -> None:
    problems = gw.validate_result_summary({"id": 1})
    assert any("missing fields" in p for p in problems)
