"""Contract tests for the formulas gateway client.

Layer: contracts (docs/TEST_STRATEGIES.md §4.3). Asserts, against golden
JSON fixtures in tests/contracts/fixtures/formulas/: *given this service
response, the gateway accepts it; given a malformed one, it rejects it
with a clear error.* No network — the response validator is pure, and the
one end-to-end check fakes the store via monkeypatch.
"""
import json
from pathlib import Path

import pytest

from backend.gateway import formulas as gw
from backend.services.formulas import store

FIXTURES = Path(__file__).parent / "fixtures" / "formulas"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.mark.parametrize("name", ["valid_record", "valid_record_minimal"])
def test_valid_service_records_are_accepted(name: str) -> None:
    assert gw.validate_record(_fixture(name)) == []


@pytest.mark.parametrize(
    "name",
    [
        "malformed_missing_fields",
        "malformed_bad_id",
        "malformed_bad_composition",
    ],
)
def test_malformed_service_records_are_rejected(name: str) -> None:
    assert gw.validate_record(_fixture(name)) != []


def test_gateway_raises_uniform_error_on_malformed_list(monkeypatch) -> None:
    """End-to-end: a malformed service response surfaces as GatewayError."""
    monkeypatch.setattr(
        store, "list_formulas", lambda conn: [{"name": "missing every field"}]
    )
    with pytest.raises(gw.GatewayError) as exc:
        gw.list_formulas(None)
    assert exc.value.problems  # carries the contract violations


def test_gateway_fails_fast_on_invalid_create_payload() -> None:
    """Requests are validated before they reach the service (fail fast)."""
    conn = store.connect()
    try:
        with pytest.raises(gw.GatewayError) as exc:
            gw.create_formula(conn, {"name": "X", "status": "gaseous"})
        assert any("status" in p for p in exc.value.problems)
        assert store.list_formulas(conn) == []  # nothing was written
    finally:
        conn.close()


def test_gateway_update_validates_merged_record() -> None:
    conn = store.connect()
    try:
        record = gw.create_formula(conn, {"name": "X", "status": "draft"})
        with pytest.raises(gw.GatewayError) as exc:
            gw.update_formula(conn, record["id"], {"status": "gaseous"})
        assert any("status" in p for p in exc.value.problems)
        # record unchanged
        assert gw.get_formula(conn, record["id"])["status"] == "draft"
    finally:
        conn.close()


def test_gateway_create_duplicate_and_versions() -> None:
    conn = store.connect()
    try:
        record = gw.create_formula(conn, {"name": "X", "status": "draft"})
        assert record["version"] == 1

        dup = gw.duplicate_formula(conn, record["id"])
        assert dup["id"] != record["id"]
        assert dup["name"] == "Copy of X"
        assert dup["version"] == 1

        versions = gw.list_formula_versions(conn, record["id"])
        assert len(versions) == 1
        assert versions[0]["version"] == 1
    finally:
        conn.close()
