"""Contract tests for the ingredients gateway client.

Layer: contracts (docs/TEST_STRATEGIES.md §4.3). Asserts, against golden
JSON fixtures in tests/contracts/fixtures/ingredients/: *given this
service response, the gateway accepts it; given a malformed one, it
rejects it with a clear error.* No network — the response validator is
pure, and the one end-to-end check fakes the store via monkeypatch.
"""
import json
from pathlib import Path

import pytest

from backend.gateway import ingredients as gw
from backend.services.ingredients import store

FIXTURES = Path(__file__).parent / "fixtures" / "ingredients"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@pytest.mark.parametrize("name", ["valid_record", "valid_record_minimal"])
def test_valid_service_records_are_accepted(name: str) -> None:
    assert gw.validate_record(_fixture(name)) == []


@pytest.mark.parametrize(
    "name",
    ["malformed_missing_fields", "malformed_bad_id", "malformed_bad_custom_fields"],
)
def test_malformed_service_records_are_rejected(name: str) -> None:
    assert gw.validate_record(_fixture(name)) != []


def test_gateway_raises_uniform_error_on_malformed_list(monkeypatch) -> None:
    """End-to-end: a malformed service response surfaces as GatewayError."""
    monkeypatch.setattr(
        store, "list_ingredients", lambda conn: [{"name": "missing every field"}]
    )
    with pytest.raises(gw.GatewayError) as exc:
        gw.list_ingredients(None)
    assert exc.value.problems  # carries the contract violations


def test_gateway_fails_fast_on_invalid_create_payload() -> None:
    """Requests are validated before they reach the service (fail fast)."""
    conn = store.connect()
    try:
        with pytest.raises(gw.GatewayError) as exc:
            gw.create_ingredient(conn, {"state": "gaseous"})
        assert any("name" in p for p in exc.value.problems)
        assert any("state" in p for p in exc.value.problems)
        assert store.list_ingredients(conn) == []  # nothing was written
    finally:
        conn.close()


def test_gateway_update_validates_merged_record() -> None:
    conn = store.connect()
    try:
        record = gw.create_ingredient(conn, {"name": "Water"})
        with pytest.raises(gw.GatewayError) as exc:
            gw.update_ingredient(conn, record["id"], {"state": "gaseous"})
        assert any("state" in p for p in exc.value.problems)
        # record unchanged
        assert gw.get_ingredient(conn, record["id"])["state"] is None
    finally:
        conn.close()
