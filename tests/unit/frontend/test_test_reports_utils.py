"""Unit tests for the Test Reports frontend pure helpers.

Layer: unit — frontend (docs/TEST_STRATEGIES.md §4.2). No streamlit.
"""
from datetime import date

from frontend.test_reports import utils


# --- parse_date ------------------------------------------------------------

def test_parse_date_variants() -> None:
    assert utils.parse_date("2026-09-20") == date(2026, 9, 20)
    assert utils.parse_date("2026-09-20T09:00:00") == date(2026, 9, 20)
    assert utils.parse_date(date(2026, 9, 20)) == date(2026, 9, 20)
    assert utils.parse_date("") is None
    assert utils.parse_date(None) is None
    assert utils.parse_date("last tuesday") is None


# --- payload builders ------------------------------------------------------

def test_build_report_payload_blank_strings_become_none() -> None:
    payload = utils.build_report_payload(
        test_method="  Sensory panel ",
        evaluation_date="2026-09-20",
        person_in_charge="",
        methodology=None,
        notes="  ",
    )
    assert payload == {
        "test_method": "Sensory panel",
        "evaluation_date": "2026-09-20",
        "person_in_charge": None,
        "methodology": None,
        "equipment": None,
        "panel": None,
        "notes": None,
    }


def test_build_result_payload() -> None:
    payload = utils.build_result_payload(
        sample_id=1,
        transfer_id=2,
        parameter=" pH ",
        value=6.5,
        unit="",
        notes="re-read",
    )
    assert payload == {
        "sample_id": 1,
        "transfer_id": 2,
        "parameter": "pH",
        "value": 6.5,
        "unit": None,
        "notes": "re-read",
    }


# --- overview --------------------------------------------------------------

def test_overview_rows_use_result_stats() -> None:
    reports = [
        {
            "id": 1,
            "test_method": "Sensory panel",
            "evaluation_date": "2026-09-20",
            "person_in_charge": None,
        },
        {
            "id": 2,
            "test_method": "Stability",
            "evaluation_date": "2026-09-21",
            "person_in_charge": "ducphu",
        },
    ]
    rows = utils.overview_rows(
        reports, result_stats={1: {"results": 3, "samples": 2}}
    )
    assert rows[0] == {
        "id": 1,
        "method": "Sensory panel",
        "date": "2026-09-20",
        "in_charge": "—",
        "samples": 2,
        "results": 3,
    }
    # report with no results yet
    assert rows[1]["samples"] == 0
    assert rows[1]["results"] == 0
    assert rows[1]["in_charge"] == "ducphu"


# --- labels ----------------------------------------------------------------

def test_transfer_label() -> None:
    assert utils.transfer_label(None) == "—"
    assert (
        utils.transfer_label(
            {"kind": "retention", "sent_at": "2026-09-15"}
        )
        == "retention · 2026-09-15"
    )
    assert (
        utils.transfer_label(
            {"kind": "dispatch", "to_team": "shelf-life", "sent_at": "2026-10-01"}
        )
        == "shelf-life · 2026-10-01"
    )
    # dispatch without a team falls back to the kind
    assert (
        utils.transfer_label({"kind": "dispatch", "sent_at": "2026-10-01"})
        == "dispatch · 2026-10-01"
    )


def test_result_rows_resolve_sample_and_transfer() -> None:
    results = [
        {
            "id": 1,
            "report_id": 9,
            "sample_id": 3,
            "transfer_id": 5,
            "parameter": "Overall liking",
            "value": 7.5,
            "unit": "pts",
            "notes": None,
        }
    ]
    rows = utils.result_rows(
        results,
        sample_index={3: {"id": 3, "sample_code": "4A8"}},
        transfer_index={5: {"id": 5, "kind": "retention", "sent_at": "2026-09-15"}},
    )
    assert rows[0]["sample"] == "4A8"
    assert rows[0]["transfer"] == "retention · 2026-09-15"
    assert rows[0]["value"] == 7.5
    assert rows[0]["unit"] == "pts"


def test_result_rows_fall_back_to_ids() -> None:
    rows = utils.result_rows(
        [
            {
                "id": 1,
                "sample_id": 3,
                "transfer_id": 5,
                "parameter": "pH",
                "value": 6.5,
                "unit": None,
                "notes": None,
            }
        ]
    )
    assert rows[0]["sample"] == "#3"
    assert rows[0]["transfer"] == "—"


# --- option labels ---------------------------------------------------------

def test_sample_options() -> None:
    labels, label_to_id = utils.sample_options(
        [
            {"id": 1, "sample_code": "4A8", "origin": "batch"},
            {"id": 2, "sample_code": "BM1", "origin": "benchmark"},
        ]
    )
    assert labels == ["4A8 — batch", "BM1 — benchmark"]
    assert label_to_id == {"4A8 — batch": 1, "BM1 — benchmark": 2}


def test_transfer_options_prefix_ids_for_uniqueness() -> None:
    labels, label_to_id = utils.transfer_options(
        [
            {"id": 5, "kind": "retention", "sent_at": "2026-09-15"},
            {
                "id": 6,
                "kind": "dispatch",
                "to_team": "shelf-life",
                "sent_at": "2026-10-01",
            },
        ]
    )
    assert labels == [
        "#5 · retention · 2026-09-15",
        "#6 · shelf-life · 2026-10-01",
    ]
    assert label_to_id["#5 · retention · 2026-09-15"] == 5
