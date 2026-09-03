"""Contract tests for the batches gateway client.

Layer: contracts (docs/TEST_STRATEGIES.md §4.3). Asserts, against golden
JSON fixtures in tests/contracts/fixtures/batches/: *given this service
response, the gateway accepts it; given a malformed one, it rejects it
with a clear error.* No network — the response validator is pure.
"""
import json
from pathlib import Path

import pytest

from backend.gateway import batches as gw

FIXTURES = Path(__file__).parent / "fixtures" / "batches"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.mark.parametrize("name", ["valid_record", "valid_record_minimal"])
def test_valid_service_records_are_accepted(name: str) -> None:
    assert gw.validate_record(_fixture(name)) == []


@pytest.mark.parametrize(
    "name",
    [
        "malformed_missing_fields",
        "malformed_bad_fields",
    ],
)
def test_malformed_service_records_are_rejected(name: str) -> None:
    assert gw.validate_record(_fixture(name)) != []


def test_malformed_reports_the_missing_fields(name: str = "malformed_missing_fields") -> None:
    problems = gw.validate_record(_fixture(name))
    assert any("missing fields" in p for p in problems)
    assert any(field in problems[0] for field in ("id", "batch_code"))


def test_record_with_partial_actual_is_accepted() -> None:
    """The contract mirrors what the service actually returns: actual rows
    accumulate over time, so shape checks stay permissive on content."""
    record = _fixture("valid_record")
    record["actual"] = {"composition": [], "observations": "started"}
    assert gw.validate_record(record) == []
