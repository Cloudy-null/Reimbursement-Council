"""Checks on what the local model read. Pure logic, no I/O.

The model only reads. It copies values as printed; this module turns them into our formats and
keeps a value only when every check passes:
1. Schema: the answer must be valid JSON in the agreed shape (parse_answer), else it is dropped.
2. Grounding: the value must appear in the OCR text or the QR code. Otherwise it is "made up".
3. QR as truth: total, date and VAT number are compared with the QR code; mismatches counted.
4. Plausibility: amount above zero, date not in the future and in the year range, VAT number
   format from config.
Arithmetic (items sum, VAT 15 percent) runs later on every reading in core/extraction.py.
"""

import json
import re
from collections import Counter
from datetime import date, timedelta
from difflib import SequenceMatcher
from typing import Literal

from pydantic import ValidationError

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import ExtractedField, LineItem
from reimbursement_council.core.models.common import DocumentKind, FieldName, Model
from reimbursement_council.core.money import parse_sar_to_halalas
from reimbursement_council.core.receipt_parsing import MONEY_PATTERN, first_date, fix_digits
from reimbursement_council.core.text import normalize_text
from reimbursement_council.core.zatca import ZatcaInvoice

_TIME = re.compile(r"(\d{1,2}):(\d{2})")
NAME_FIELDS: tuple[FieldName, ...] = ("provider_name", "patient_name")
MONEY_NAMES: tuple[FieldName, ...] = ("subtotal", "vat_total", "total")


class VisionItem(Model):
    description: str
    quantity: str | None
    amount: str | None


class VisionAnswer(Model):
    """The model's answer, values as printed. Any other shape is refused."""

    document_kind: DocumentKind
    provider_name: str | None
    vat_number: str | None
    date: str | None
    time: str | None
    patient_name: str | None
    subtotal: str | None
    vat_total: str | None
    total: str | None
    items: list[VisionItem]


def _nullable() -> dict[str, object]:
    return {"type": ["string", "null"]}


ANSWER_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "document_kind": {
            "type": "string",
            "enum": ["invoice", "receipt", "prescription", "medical_report", "other"],
        },
        **{
            name: _nullable()
            for name in VisionAnswer.model_fields
            if name not in {"document_kind", "items"}
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantity": _nullable(),
                    "amount": _nullable(),
                },
                "required": ["description", "quantity", "amount"],
            },
        },
    },
    "required": list(VisionAnswer.model_fields),
}


def parse_answer(text: str) -> VisionAnswer | None:
    """The answer, or None when it is not valid JSON in the agreed shape (check 1)."""
    try:
        return VisionAnswer.model_validate(json.loads(text))
    except (ValueError, ValidationError):
        return None


class Evidence(Model):
    """What the OCR and the QR code show on the same document."""

    text: str
    raw: str
    money: set[int]
    dates: set[date]
    digits: str
    qr: ZatcaInvoice | None


def evidence_from(
    text_lines: list[str], qr: ZatcaInvoice | None, years: tuple[int, int]
) -> Evidence:
    rows = [fix_digits(line)[0] for line in text_lines]
    money = {
        int(whole.replace(",", "")) * 100 + int(cents)
        for row in rows
        for whole, cents in MONEY_PATTERN.findall(row)
    }
    dates = {found[0] for row in rows if (found := first_date(row, years)) is not None}
    return Evidence(
        text=normalize_text(" ".join(rows)),
        raw=" ".join(rows),
        money=money,
        dates=dates,
        digits="".join(c for c in "".join(rows) if c.isdigit()),
        qr=qr,
    )


def money_value(text: str) -> int | None:
    """Printed money to halalas: '1,150.50', 'RM 14.10', '345.00 SAR'."""
    direct = parse_sar_to_halalas(text)
    if direct is not None:
        return direct
    found = MONEY_PATTERN.findall(fix_digits(text)[0])
    if len(found) != 1:
        return None
    whole, cents = found[0]
    return int(whole.replace(",", "")) * 100 + int(cents)


def name_is_printed(value: str, text: str, ratio: float) -> bool:
    """The name, or something very close to it, appears in the text (small OCR noise allowed)."""
    target = normalize_text(value)
    if not target or not text:
        return False
    if target in text:
        return True
    size = len(target)
    return any(
        SequenceMatcher(None, target, text[start : start + size]).ratio() >= ratio
        for start in range(max(1, len(text) - size + 1))
    )


def _digits_printed(digits: str, all_digits: str) -> bool:
    if digits in all_digits:
        return True
    size = len(digits)
    return any(
        sum(a != b for a, b in zip(digits, all_digits[i : i + size], strict=True)) <= 1
        for i in range(max(0, len(all_digits) - size + 1))
    )


Verdict = Literal["kept", "made_up", "implausible", "unparsed"]


class Checked(Model):
    fields: list[ExtractedField]
    items: list[LineItem]
    kind: DocumentKind
    counts: dict[str, int]


def _check(
    name: FieldName, raw: str, evidence: Evidence, uploaded: date, settings: Settings
) -> tuple[Verdict, str | None]:
    """One value: its normalized form, or why it is dropped."""
    cfg = settings.decision.vision
    years = (settings.decision.ocr.min_date_year, settings.decision.ocr.max_date_year)
    qr = evidence.qr
    if name in MONEY_NAMES:
        amount = money_value(raw)
        if amount is None:
            return "unparsed", None
        if amount <= 0:
            return "implausible", None
        qr_money = set() if qr is None else {qr.total_with_vat, qr.vat_total}
        return ("kept" if amount in evidence.money | qr_money else "made_up"), str(amount)
    if name == "treatment_date":
        found = first_date(fix_digits(raw)[0], years)
        if found is None:
            return "unparsed", None
        day = found[0]
        if day > uploaded + timedelta(days=cfg.future_days):
            return "implausible", None
        qr_day = None if qr is None else date.fromisoformat(qr.timestamp[:10])
        return ("kept" if day in evidence.dates or day == qr_day else "made_up"), day.isoformat()
    if name == "vat_number":
        digits = "".join(c for c in fix_digits(raw)[0] if c.isdigit())
        if not re.fullmatch(cfg.vat_number_pattern, digits):
            return "implausible", None
        printed = _digits_printed(digits, evidence.digits) or (
            qr is not None and qr.vat_number == digits
        )
        return ("kept" if printed else "made_up"), digits
    value = raw.strip()
    if not value:
        return "unparsed", None
    on_qr = qr is not None and name == "provider_name" and qr.seller_name.strip() == value
    printed = on_qr or name_is_printed(value, evidence.text, cfg.ground_ratio)
    return ("kept" if printed else "made_up"), value


def _qr_mismatches(values: dict[FieldName, str], qr: ZatcaInvoice | None) -> tuple[int, int]:
    """(compared, mismatched) for total, date and VAT number against the QR code (check 3)."""
    if qr is None:
        return 0, 0
    truth: dict[FieldName, str] = {
        "total": str(qr.total_with_vat),
        "treatment_date": qr.timestamp[:10],
        "vat_number": qr.vat_number,
    }
    compared = [name for name in truth if name in values]
    return len(compared), sum(values[name] != truth[name] for name in compared)


def _items(
    answer: VisionAnswer, evidence: Evidence, settings: Settings
) -> tuple[list[LineItem], Counter[str]]:
    counts: Counter[str] = Counter()
    items: list[LineItem] = []
    for item in answer.items:
        counts["items_returned"] += 1
        amount = None if item.amount is None else money_value(item.amount)
        described = name_is_printed(
            item.description, evidence.text, settings.decision.vision.ground_ratio
        )
        if amount is None or amount <= 0 or amount not in evidence.money or not described:
            counts["items_made_up"] += 1
            continue
        quantity_text = "".join(c for c in (item.quantity or "1") if c.isdigit()) or "1"
        quantity = max(1, int(quantity_text))
        unit = amount // quantity if amount % quantity == 0 else amount
        items.append(
            LineItem(
                description=item.description.strip(),
                service_code=None,
                quantity=quantity if unit * quantity == amount else 1,
                unit_price=unit,
                amount=amount,
                confidence=settings.decision.vision.field_confidence,
            )
        )
    return items, counts


def checked_answer(
    answer: VisionAnswer, evidence: Evidence, document_id: str, uploaded: date, settings: Settings
) -> Checked:
    """Every value the model returned that passed the checks, as fields; counts for the harness."""
    raw: dict[FieldName, str | None] = {
        "provider_name": answer.provider_name,
        "vat_number": answer.vat_number,
        "treatment_date": answer.date,
        "patient_name": answer.patient_name,
        "subtotal": answer.subtotal,
        "vat_total": answer.vat_total,
        "total": answer.total,
    }
    counts: Counter[str] = Counter()
    kept: dict[FieldName, str] = {}
    fields: list[ExtractedField] = []
    for name, value in raw.items():
        if value is None or not value.strip():
            continue
        counts["returned"] += 1
        verdict, normalized = _check(name, value, evidence, uploaded, settings)
        counts[verdict] += 1
        if verdict != "kept" or normalized is None:
            continue
        kept[name] = normalized
        fields.append(
            ExtractedField(
                document_id=document_id,
                name=name,
                value=normalized,
                original_text=value,
                source="vision",
                confidence=settings.decision.vision.field_confidence,
            )
        )
    time_match = None if answer.time is None else _TIME.search(answer.time)
    if "treatment_date" in kept and time_match and time_match.group(0) in evidence.raw:
        hour, minute = time_match.groups()
        stamp = f"{kept['treatment_date']}T{int(hour):02d}:{minute}:00"
        fields.append(
            ExtractedField(
                document_id=document_id,
                name="invoice_timestamp",
                value=stamp,
                original_text=answer.time or "",
                source="vision",
                confidence=settings.decision.vision.field_confidence,
            )
        )
    compared, mismatched = _qr_mismatches(kept, evidence.qr)
    counts["qr_compared"] += compared
    counts["qr_mismatch"] += mismatched
    items, item_counts = _items(answer, evidence, settings)
    counts.update(item_counts)
    return Checked(fields=fields, items=items, kind=answer.document_kind, counts=dict(counts))
