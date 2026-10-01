"""Pure helpers for the Samples pages (no streamlit).

Extracted so they are unit-testable without a UI runtime
(docs/TEST_STRATEGIES.md §4.2). Mirrors the frontend.batches.utils /
frontend.formulas.utils patterns: page files stay thin glue.

Covers the v0 sample logic (frontend/samples/README.md): identity (3-char
code suggestion + normalization, Q3/Q11), the derived age in weeks (Q2),
overview rows/stats (Q6/Q13), the dispatch filter and the delete-guard
reason (Q8/Q12).
"""
from __future__ import annotations

import random
from datetime import date, datetime
from typing import Any, Iterable

import pandas as pd

from backend.services.samples.schema import (
    SAMPLE_CODE_ALPHABET,
    SAMPLE_CODE_LENGTH,
)

# Overview table widget key — its selection can go stale when a selected
# row is deleted; the delete dialog resets it (mirrors Formulas/Batches).
SAMPLES_TABLE_KEY = "samples_table"

# Transfers tab display columns, in display order.
TRANSFER_DISPLAY_COLUMNS = ("kind", "team", "sent", "storage", "by", "notes")


def _cell_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


# --- identity (README Q3/Q11) ---------------------------------------------

def normalize_sample_code(text: object) -> str:
    """Strip and uppercase a typed code before it is validated/stored."""
    return _cell_text(text).strip().upper()


def suggest_sample_code(
    existing: Iterable[str] | None = None,
    rng: random.Random | None = None,
) -> str:
    """A random 3-char code not already in ``existing`` (Q3/Q11).

    Falls back to the first free code in the alphabet when random draws
    keep colliding (only reachable with an almost-exhausted code space), so
    the suggestion is always free of the codes it was given.
    """
    used = {normalize_sample_code(code) for code in (existing or [])}
    rng = rng or random
    for _ in range(50):
        code = "".join(
            rng.choice(SAMPLE_CODE_ALPHABET)
            for _ in range(SAMPLE_CODE_LENGTH)
        )
        if code not in used:
            return code
    for first in SAMPLE_CODE_ALPHABET:
        for second in SAMPLE_CODE_ALPHABET:
            for third in SAMPLE_CODE_ALPHABET:
                code = first + second + third
                if code not in used:
                    return code
    return "".join(
        rng.choice(SAMPLE_CODE_ALPHABET) for _ in range(SAMPLE_CODE_LENGTH)
    )


# --- dates / age in weeks (README Q2) -------------------------------------

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


def weeks_since(taken_at: object, today: date | None = None) -> int | None:
    """Completed weeks since the sample's taken date (README Q2).

    Returns None when the date cannot be parsed; future dates count as 0
    weeks.
    """
    taken = parse_date(taken_at)
    if taken is None:
        return None
    reference = parse_date(today) or date.today()
    days = max(0, (reference - taken).days)
    return days // 7


# --- selectors on transfers -----------------------------------------------

def retention(transfers: list[dict] | None) -> dict | None:
    for transfer in transfers or []:
        if transfer.get("kind") == "retention":
            return transfer
    return None


def dispatches(transfers: list[dict] | None) -> list[dict]:
    return [t for t in (transfers or []) if t.get("kind") == "dispatch"]


def transfer_count(
    transfers: list[dict] | None, kind: str | None = None
) -> int:
    if kind is None:
        return len(transfers or [])
    return len([t for t in (transfers or []) if t.get("kind") == kind])


def transfer_rows(transfers: list[dict] | None) -> list[dict]:
    """Transfer records -> newest-first display rows (README §4)."""

    def _key(transfer: dict) -> tuple:
        return (_cell_text(transfer.get("sent_at")), transfer.get("id") or 0)

    rows = []
    for transfer in sorted(transfers or [], key=_key, reverse=True):
        rows.append(
            {
                "kind": transfer.get("kind"),
                "team": transfer.get("to_team") or "—",
                "sent": transfer.get("sent_at") or "—",
                "storage": transfer.get("storage_condition") or "—",
                "by": transfer.get("sent_by") or "—",
                "notes": transfer.get("notes") or "",
            }
        )
    return rows


# --- overview --------------------------------------------------------------

def origin_label(
    record: dict, batch_index: dict[int, dict] | None = None
) -> str:
    """Display label for a sample's origin (Q1/Q14)."""
    if record.get("origin") == "benchmark":
        return "benchmark"
    batch = (batch_index or {}).get(record.get("batch_id")) or {}
    code = batch.get("batch_code") or f"#{record.get('batch_id')}"
    return f"batch {code}"


def overview_rows(
    records: list[dict],
    batch_index: dict[int, dict] | None = None,
    transfer_counts: dict[int, dict[str, int]] | None = None,
    report_counts: dict[int, int] | None = None,
) -> list[dict]:
    """Sample records -> overview table rows (README §4).

    The dispatch column counts real handoffs (Q13, owner decision
    2026-09-15); the report column counts distinct test reports per
    sample (Test Reports reverse link, live 2026-10-01).
    """
    batch_index = batch_index or {}
    transfer_counts = transfer_counts or {}
    report_counts = report_counts or {}
    rows = []
    for record in records:
        counts = transfer_counts.get(record["id"]) or {}
        rows.append(
            {
                "id": record["id"],
                "code": record["sample_code"],
                "origin": origin_label(record, batch_index),
                "status": record["status"],
                "taken": (record.get("taken_at") or "")[:10],
                "age_weeks": weeks_since(record.get("taken_at")),
                "dispatches": counts.get("dispatches", 0),
                "reports": report_counts.get(record["id"], 0),
            }
        )
    return rows


def filter_samples(
    records: list[dict],
    status: str | None = None,
    batch_id: int | None = None,
) -> list[dict]:
    """Filter sample records by status and/or batch (README §4).

    ``None`` means "no filter" for either dimension.
    """
    result = list(records or [])
    if status is not None:
        result = [r for r in result if r.get("status") == status]
    if batch_id is not None:
        result = [r for r in result if r.get("batch_id") == batch_id]
    return result


def batch_options(
    batches: list[dict],
) -> tuple[list[str], dict[str, int]]:
    """Display labels + label -> batch id for the origin picker.

    Labels are ``"B-0001 — name"``; duplicate names cannot collide because
    the batch code is unique.
    """
    options: list[str] = []
    label_to_id: dict[str, int] = {}
    for batch in batches or []:
        code = batch.get("batch_code") or f"#{batch.get('id')}"
        label = f"{code} — {batch.get('name')}" if batch.get("name") else code
        options.append(label)
        label_to_id[label] = int(batch["id"])
    return options, label_to_id


# --- delete guard (README Q8/Q12) -----------------------------------------

def sample_delete_block_reason(
    dispatch_count: int | None, report_count: int | None = 0
) -> str | None:
    """Why a sample cannot be deleted, or None when deletion is allowed.

    Dispatches block; test reports block (live, Test Reports Q13); the
    retention row never blocks (Q12).
    """
    parts: list[str] = []
    reports = report_count or 0
    if reports > 0:
        parts.append(
            f"{reports} test report{'s' if reports != 1 else ''}"
        )
    dispatch = dispatch_count or 0
    if dispatch > 0:
        parts.append(
            f"{dispatch} dispatch transfer{'s' if dispatch != 1 else ''}"
        )
    if not parts:
        return None
    return "it has " + " and ".join(parts) + " recorded."


# --- payload builders ------------------------------------------------------

def build_sample_payload(
    sample_code: str,
    origin: str,
    batch_id: int | None = None,
    source: str = "",
    taken_at: str = "",
    status: str = "active",
    notes: str = "",
    retention_storage: str = "",
) -> dict:
    """Create-dialog values -> a service payload (blank strings -> None).

    The retention transfer always defaults ``sent_at`` to the sample's
    taken date (README Q7).
    """
    return {
        "sample_code": normalize_sample_code(sample_code),
        "origin": origin,
        "batch_id": batch_id,
        "source": _cell_text(source).strip() or None,
        "taken_at": taken_at,
        "status": status,
        "notes": _cell_text(notes).strip() or None,
        "retention": {
            "sent_at": taken_at,
            "storage_condition": retention_storage,
            "sent_by": None,
            "notes": None,
        },
    }


def build_transfer_payload(
    to_team: str,
    sent_at: str,
    storage_condition: str,
    sent_by: str = "",
    notes: str = "",
) -> dict:
    """Dispatch dialog values -> a service transfer payload."""
    return {
        "kind": "dispatch",
        "to_team": _cell_text(to_team).strip(),
        "sent_at": sent_at,
        "storage_condition": storage_condition,
        "sent_by": _cell_text(sent_by).strip() or None,
        "notes": _cell_text(notes).strip() or None,
    }
