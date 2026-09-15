"""Contract tests for the samples gateway client.

Layer: contracts (docs/TEST_STRATEGIES.md §4.3). Asserts, against golden
JSON fixtures in tests/contracts/fixtures/samples/: *given this service
response, the gateway accepts it; given a malformed one, it rejects it
with a clear error.* No network — the response validators are pure.
"""
import json
from pathlib import Path

import pytest

from backend.gateway import samples as gw

FIXTURES = Path(__file__).parent / "fixtures" / "samples"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.mark.parametrize(
    "name", ["valid_sample", "valid_sample_benchmark"]
)
def test_valid_sample_records_are_accepted(name: str) -> None:
    assert gw.validate_record(_fixture(name)) == []


@pytest.mark.parametrize(
    "name",
    ["malformed_sample_missing_fields", "malformed_sample_bad_fields"],
)
def test_malformed_sample_records_are_rejected(name: str) -> None:
    assert gw.validate_record(_fixture(name)) != []


def test_malformed_sample_reports_the_missing_fields() -> None:
    problems = gw.validate_record(_fixture("malformed_sample_missing_fields"))
    assert any("missing fields" in p for p in problems)
    assert any(
        field in problems[0]
        for field in ("sample_code", "status", "batch_id")
    )


@pytest.mark.parametrize(
    "name", ["valid_transfer_retention", "valid_transfer_dispatch"]
)
def test_valid_transfer_records_are_accepted(name: str) -> None:
    assert gw.validate_transfer_record(_fixture(name)) == []


def test_malformed_transfer_record_is_rejected() -> None:
    assert gw.validate_transfer_record(_fixture("malformed_transfer")) != []


def test_benchmark_sample_with_null_batch_is_accepted() -> None:
    record = _fixture("valid_sample_benchmark")
    record["batch_id"] = None
    assert gw.validate_record(record) == []
