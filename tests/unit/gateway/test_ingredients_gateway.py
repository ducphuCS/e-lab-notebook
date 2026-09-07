"""Unit tests for the ingredients gateway's TEMP legacy migration path.

Layer: unit — gateway (docs/TEST_STRATEGIES.md §4.1/§6): the gateway is
headless (no streamlit) and calls the store in-process. Documents the
purpose of the temporary migration: legacy-format rows fail the strict
read (response validation) until they are rewritten in place. Delete this
file with the migration (frontend/ingredients/README.md §11).
"""
import pytest

from backend.gateway import ingredients as gw
from backend.services.ingredients import store


@pytest.fixture()
def conn():
    connection = store.connect()  # in-memory
    yield connection
    connection.close()


def test_legacy_row_blocks_read_until_migrated(conn) -> None:
    # v0 wrote custom_fields as plain strings; the gateway refuses to write
    # that shape now, so seed it through the (validation-free) store.
    store.create_ingredient(
        conn, {"name": "Water", "custom_fields": {"pH": "7"}}
    )

    # read path rejects the legacy shape...
    with pytest.raises(gw.GatewayError):
        gw.list_ingredients(conn)

    # ...the migration path finds it, rewrites it, and unblocks the read.
    assert gw.count_legacy_custom_field_rows(conn) == 1
    assert gw.migrate_legacy_custom_fields(conn) == 1
    assert gw.count_legacy_custom_field_rows(conn) == 0
    records = gw.list_ingredients(conn)
    assert records[0]["custom_fields"] == {"pH": {"value": "7", "unit": ""}}

    # idempotent — nothing left to migrate
    assert gw.migrate_legacy_custom_fields(conn) == 0


def test_only_legacy_rows_are_migrated(conn) -> None:
    store.create_ingredient(conn, {"name": "Old", "custom_fields": {"grade": "tech"}})
    store.create_ingredient(
        conn,
        {"name": "New", "custom_fields": {"pH": {"value": "7", "unit": "mg/L"}}},
    )
    store.create_ingredient(conn, {"name": "Plain"})

    assert gw.count_legacy_custom_field_rows(conn) == 1
    assert gw.migrate_legacy_custom_fields(conn) == 1
    assert gw.count_legacy_custom_field_rows(conn) == 0

    by_name = {r["name"]: r["custom_fields"] for r in gw.list_ingredients(conn)}
    assert by_name["Old"] == {"grade": {"value": "tech", "unit": ""}}
    assert by_name["New"] == {"pH": {"value": "7", "unit": "mg/L"}}
    assert by_name["Plain"] == {}


def test_empty_database_needs_no_migration(conn) -> None:
    assert gw.count_legacy_custom_field_rows(conn) == 0
    assert gw.migrate_legacy_custom_fields(conn) == 0
