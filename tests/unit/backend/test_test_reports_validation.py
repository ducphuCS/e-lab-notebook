"""Unit tests for test-report and test-result validation.

Layer: unit — backend (docs/TEST_STRATEGIES.md §4.1).
"""
from backend.services.test_reports.validation import (
    is_iso_date,
    is_number,
    validate_report,
    validate_result,
)


def _report(**overrides) -> dict:
    data = {
        "test_method": "Sensory panel",
        "evaluation_date": "2026-09-20",
        "person_in_charge": "ducphu",
        "methodology": "9-point hedonic",
        "equipment": None,
        "panel": "trained panel A",
        "notes": None,
    }
    data.update(overrides)
    return data


def _result(**overrides) -> dict:
    data = {
        "report_id": 1,
        "sample_id": 3,
        "transfer_id": 5,
        "parameter": "Overall liking",
        "value": 7.5,
        "unit": "pts",
        "notes": None,
    }
    data.update(overrides)
    return data


# --- helpers ---------------------------------------------------------------

def test_is_iso_date() -> None:
    assert is_iso_date("2026-09-20") is True
    assert is_iso_date("2026-13-01") is False
    assert is_iso_date("") is False
    assert is_iso_date(None) is False


def test_is_number_rejects_bool() -> None:
    assert is_number(7.5) is True
    assert is_number(7) is True
    assert is_number(True) is False
    assert is_number("7.5") is False
    assert is_number(None) is False


# --- report validation -----------------------------------------------------

def test_valid_report_passes() -> None:
    assert validate_report(_report()) == []


def test_report_minimal_passes() -> None:
    assert validate_report(
        {"test_method": "Stability", "evaluation_date": "2026-09-20"}
    ) == []


def test_test_method_required_non_empty() -> None:
    assert any("test_method" in p for p in validate_report(_report(test_method="")))
    assert any("test_method" in p for p in validate_report(_report(test_method=None)))


def test_evaluation_date_must_be_iso() -> None:
    assert any(
        "evaluation_date" in p
        for p in validate_report(_report(evaluation_date="last tuesday"))
    )
    assert any(
        "evaluation_date" in p
        for p in validate_report(_report(evaluation_date=None))
    )


def test_report_optional_strings_are_type_checked() -> None:
    problems = validate_report(_report(person_in_charge=5, equipment=1))
    assert any("person_in_charge" in p for p in problems)
    assert any("equipment" in p for p in problems)


# --- result validation -----------------------------------------------------

def test_valid_result_passes() -> None:
    assert validate_result(_result()) == []


def test_result_identifiers_required_ints() -> None:
    problems = validate_result(_result(report_id="1"))
    assert any("report_id" in p for p in problems)
    problems = validate_result(_result(sample_id=None))
    assert any("sample_id" in p for p in problems)
    problems = validate_result(_result(transfer_id=True))
    assert any("transfer_id" in p for p in problems)


def test_parameter_required_non_empty() -> None:
    assert any("parameter" in p for p in validate_result(_result(parameter="  ")))
    assert any("parameter" in p for p in validate_result(_result(parameter=None)))


def test_value_must_be_a_number() -> None:
    assert any("value" in p for p in validate_result(_result(value="high")))
    assert any("value" in p for p in validate_result(_result(value=True)))
    assert any("value" in p for p in validate_result(_result(value=None)))


def test_result_optional_strings_are_type_checked() -> None:
    problems = validate_result(_result(unit=5, notes=1))
    assert any("unit" in p for p in problems)
    assert any("notes" in p for p in problems)
