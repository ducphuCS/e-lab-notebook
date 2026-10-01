"""Pure helpers for the Test Reports pages (no streamlit).

Extracted so they are unit-testable without a UI runtime
(docs/TEST_STRATEGIES.md §4.2). Mirrors the frontend.samples.utils
pattern: page files stay thin glue.

Covers the v0 report logic (frontend/test_reports/README.md): overview
rows/stats (§4), result display rows and payload builders (§5), and the
sample/transfer labels the result dialog needs (§7).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

import pandas as pd

# Table widget keys — selection can go stale when the selected row is
# deleted; delete handlers reset them (mirrors Samples/Batches).
REPORTS_TABLE_KEY = "test_reports_table"

# Results tab display columns, in display order.
RESULT_DISPLAY_COLUMNS = ("sample", "transfer", "parameter", "value", "unit", "notes")

# v0 ships one generic report template (README Q3/Q4): the method is a
# free-text label until Test Methods lands.
DEFAULT_TEST_METHOD = "General evaluation"


def _cell_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def parse_date(value: object) -> date | None:
    """Coerce a stored date string / date / datetime to a ``date``."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _cell_text(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


# --- payload builders ------------------------------------------------------

def build_report_payload(
    test_method: str,
    evaluation_date: str,
    person_in_charge: str = "",
    methodology: str = "",
    equipment: str = "",
    panel: str = "",
    notes: str = "",
) -> dict:
    """Report-dialog values -> a service payload (blank strings -> None)."""
    return {
        "test_method": _cell_text(test_method).strip(),
        "evaluation_date": evaluation_date,
        "person_in_charge": _cell_text(person_in_charge).strip() or None,
        "methodology": _cell_text(methodology).strip() or None,
        "equipment": _cell_text(equipment).strip() or None,
        "panel": _cell_text(panel).strip() or None,
        "notes": _cell_text(notes).strip() or None,
    }


def build_result_payload(
    sample_id: int,
    transfer_id: int,
    parameter: str,
    value: float,
    unit: str = "",
    notes: str = "",
) -> dict:
    """Result-dialog values -> a service result payload (README §5)."""
    return {
        "sample_id": sample_id,
        "transfer_id": transfer_id,
        "parameter": _cell_text(parameter).strip(),
        "value": value,
        "unit": _cell_text(unit).strip() or None,
        "notes": _cell_text(notes).strip() or None,
    }


# --- overview --------------------------------------------------------------

def overview_rows(
    reports: list[dict],
    result_stats: dict[int, dict[str, int]] | None = None,
) -> list[dict]:
    """Report records -> overview table rows (README §4).

    ``samples`` is the distinct sample count per report; ``results`` the
    number of result rows (replicates included). Both derive from the
    Test Reports service, never stored.
    """
    result_stats = result_stats or {}
    rows = []
    for report in reports:
        stats = result_stats.get(report["id"]) or {}
        rows.append(
            {
                "id": report["id"],
                "method": report.get("test_method") or "—",
                "date": (report.get("evaluation_date") or "")[:10],
                "in_charge": report.get("person_in_charge") or "—",
                "samples": stats.get("samples", 0),
                "results": stats.get("results", 0),
            }
        )
    return rows


# --- results tab -----------------------------------------------------------

def transfer_label(transfer: dict | None) -> str:
    """Short human label for a sample transfer (retention / dispatch)."""
    if not transfer:
        return "—"
    kind = transfer.get("kind")
    date = (transfer.get("sent_at") or "")[:10]
    if kind == "retention":
        base = "retention"
    else:
        base = transfer.get("to_team") or "dispatch"
    return f"{base} · {date}" if date else base


def result_rows(
    results: list[dict],
    sample_index: dict[int, dict] | None = None,
    transfer_index: dict[int, dict] | None = None,
) -> list[dict]:
    """Result records -> Results-tab display rows (README §4).

    The sample and transfer are resolved through the Samples service
    indexes; a missing one falls back to ``#id`` / ``—``.
    """
    sample_index = sample_index or {}
    transfer_index = transfer_index or {}
    rows = []
    for result in results:
        sample = sample_index.get(result.get("sample_id")) or {}
        transfer = transfer_index.get(result.get("transfer_id")) or {}
        sample_label = sample.get("sample_code") or f"#{result.get('sample_id')}"
        rows.append(
            {
                "sample": sample_label,
                "transfer": transfer_label(transfer),
                "parameter": result.get("parameter") or "",
                "value": result.get("value"),
                "unit": result.get("unit") or "",
                "notes": result.get("notes") or "",
            }
        )
    return rows


# --- option labels (result dialog) -----------------------------------------

def sample_options(samples: Iterable[dict]) -> tuple[list[str], dict[str, int]]:
    """Display labels + label -> sample id for the result dialog.

    Labels are ``"4A8 — batch"``; sample codes are unique, so labels
    cannot collide.
    """
    options: list[str] = []
    label_to_id: dict[str, int] = {}
    for sample in samples or []:
        code = sample.get("sample_code") or f"#{sample.get('id')}"
        origin = sample.get("origin") or ""
        label = f"{code} — {origin}" if origin else code
        options.append(label)
        label_to_id[label] = int(sample["id"])
    return options, label_to_id


def transfer_options(
    transfers: Iterable[dict],
) -> tuple[list[str], dict[str, int]]:
    """Display labels + label -> transfer id, for a single sample.

    Transfers lack a unique human label (two dispatches to the same team
    on the same day are possible), so the label is prefixed with the id —
    unlike ``sample_options``, this keeps labels unique.
    """
    options: list[str] = []
    label_to_id: dict[str, int] = {}
    for transfer in transfers or []:
        label = f"#{transfer.get('id')} · {transfer_label(transfer)}"
        options.append(label)
        label_to_id[label] = int(transfer["id"])
    return options, label_to_id
