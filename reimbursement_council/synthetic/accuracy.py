"""Compare what the reader got from a generated receipt with the receipt's true values."""

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any

from reimbursement_council.core.models.claim import ExtractionResult
from reimbursement_council.core.text import normalize_text

FIELDS = (
    "provider_name",
    "vat_number",
    "treatment_date",
    "invoice_time",
    "patient_name",
    "subtotal",
    "vat_total",
    "total",
    "qr",
)
SAUDI = timezone(timedelta(hours=3))


def _local_time(stamp: str) -> str | None:
    try:
        moment = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(SAUDI)
    return moment.strftime("%H:%M")


def _value(reading: ExtractionResult, name: str) -> str | None:
    field = reading.best(name)  # type: ignore[arg-type]
    return None if field is None else field.value


def compare(truth: Mapping[str, Any], reading: ExtractionResult, qr_found: bool) -> dict[str, Any]:
    """True or False per field, plus (matched, total) line items."""
    result: dict[str, Any] = {}
    for name in ("vat_number", "treatment_date", "subtotal", "vat_total", "total"):
        result[name] = _value(reading, name) == truth[name]
    for name in ("provider_name", "patient_name"):
        got = _value(reading, name)
        result[name] = got is not None and normalize_text(got) in {
            normalize_text(option) for option in truth[name]
        }
    stamp = _value(reading, "invoice_timestamp")
    result["invoice_time"] = stamp is not None and _local_time(stamp) == truth["invoice_time"]
    result["qr"] = qr_found == truth["has_qr"]
    truth_items = truth["items"]
    matched = sum(
        1
        for want, got in zip(truth_items, reading.line_items, strict=False)
        if want["service_code"] == got.service_code and want["amount"] == got.amount
    )
    result["items"] = (matched, len(truth_items))
    return result


def summarize(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Share correct per field (0 to 1), item code share, and the number of receipts."""
    summary: dict[str, Any] = {"receipts": len(rows)}
    for name in FIELDS:
        summary[name] = round(sum(bool(row[name]) for row in rows) / len(rows), 3) if rows else 0.0
    matched = sum(row["items"][0] for row in rows)
    total = sum(row["items"][1] for row in rows)
    summary["item_codes"] = round(matched / total, 3) if total else 0.0
    return summary
