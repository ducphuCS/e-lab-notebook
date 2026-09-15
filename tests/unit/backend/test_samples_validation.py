"""Unit tests for sample and transfer validation.

Layer: unit — backend (docs/TEST_STRATEGIES.md §4.1).
"""
from backend.services.samples.validation import (
    is_iso_date,
    is_valid_sample_code,
    validate_sample,
    validate_transfer,
)


def _sample(**overrides) -> dict:
    data = {
        "sample_code": "4A8",
        "origin": "batch",
        "batch_id": 12,
        "source": None,
        "taken_at": "2026-09-15",
        "status": "active",
        "notes": None,
    }
    data.update(overrides)
    return data


def _transfer(**overrides) -> dict:
    data = {
        "kind": "dispatch",
        "to_team": "shelf-life",
        "sent_at": "2026-10-01",
        "storage_condition": "TA45",
        "sent_by": "ducphu",
        "notes": None,
    }
    data.update(overrides)
    return data


# --- sample code -----------------------------------------------------------

def test_is_valid_sample_code() -> None:
    assert is_valid_sample_code("4A8") is True
    assert is_valid_sample_code("ZZ9") is True
    # wrong length
    assert is_valid_sample_code("4A") is False
    assert is_valid_sample_code("4A8B") is False
    # lowercase is invalid — callers normalize before validating
    assert is_valid_sample_code("4a8") is False
    # ambiguous characters are excluded (I, L, O, 0, 1)
    for char in ("I", "L", "O", "0", "1"):
        assert is_valid_sample_code(f"A{char}B") is False
    assert is_valid_sample_code(None) is False


def test_is_iso_date() -> None:
    assert is_iso_date("2026-09-15") is True
    assert is_iso_date("2026-13-01") is False
    assert is_iso_date("") is False
    assert is_iso_date(None) is False


# --- sample validation -----------------------------------------------------

def test_valid_batch_sample_passes() -> None:
    assert validate_sample(_sample()) == []


def test_valid_benchmark_sample_passes() -> None:
    assert validate_sample(
        _sample(origin="benchmark", batch_id=None, source="Brand X")
    ) == []


def test_sample_code_format_is_checked() -> None:
    problems = validate_sample(_sample(sample_code="oops"))
    assert any("sample_code" in p for p in problems)


def test_origin_must_be_enum() -> None:
    problems = validate_sample(_sample(origin="gift"))
    assert any("origin" in p for p in problems)


def test_batch_id_required_for_batch_origin() -> None:
    problems = validate_sample(_sample(batch_id=None))
    assert any("batch_id" in p for p in problems)
    problems = validate_sample(_sample(batch_id="12"))
    assert any("batch_id" in p for p in problems)


def test_batch_id_must_be_null_for_benchmark() -> None:
    problems = validate_sample(
        _sample(origin="benchmark", batch_id=12)
    )
    assert any("batch_id" in p for p in problems)


def test_taken_at_must_be_iso_date() -> None:
    problems = validate_sample(_sample(taken_at="last tuesday"))
    assert any("taken_at" in p for p in problems)
    problems = validate_sample(_sample(taken_at=None))
    assert any("taken_at" in p for p in problems)


def test_status_must_be_enum() -> None:
    problems = validate_sample(_sample(status="lost"))
    assert any("status" in p for p in problems)


def test_optional_strings_are_type_checked() -> None:
    problems = validate_sample(_sample(source=3, notes=5))
    assert any("source" in p for p in problems)
    assert any("notes" in p for p in problems)


# --- transfer validation ---------------------------------------------------

def test_valid_dispatch_passes() -> None:
    assert validate_transfer(_transfer()) == []


def test_valid_retention_passes() -> None:
    assert (
        validate_transfer(
            _transfer(kind="retention", to_team=None)
        )
        == []
    )


def test_kind_must_be_enum() -> None:
    problems = validate_transfer(_transfer(kind="shipment"))
    assert any("kind" in p for p in problems)


def test_to_team_rules() -> None:
    problems = validate_transfer(_transfer(to_team="  "))
    assert any("to_team" in p for p in problems)
    problems = validate_transfer(
        _transfer(kind="retention", to_team="shelf-life")
    )
    assert any("to_team" in p for p in problems)


def test_sent_at_must_be_iso_date() -> None:
    problems = validate_transfer(_transfer(sent_at=None))
    assert any("sent_at" in p for p in problems)


def test_storage_condition_must_be_enum() -> None:
    problems = validate_transfer(_transfer(storage_condition="freezer"))
    assert any("storage_condition" in p for p in problems)
    problems = validate_transfer(_transfer(storage_condition=None))
    assert any("storage_condition" in p for p in problems)


def test_transfer_optional_strings_are_type_checked() -> None:
    problems = validate_transfer(_transfer(sent_by=3, notes=5))
    assert any("sent_by" in p for p in problems)
    assert any("notes" in p for p in problems)
