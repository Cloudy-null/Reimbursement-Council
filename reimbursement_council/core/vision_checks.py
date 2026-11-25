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

import re
from collections import Counter
from datetime import date, timedelta
from difflib import SequenceMatcher
from typing import Literal

from reimbursement_council.config.models import Settings
from reimbursement_council.core.dates import local_date_from_text
from reimbursement_council.core.models.claim import ExtractedField, LineItem
from reimbursement_council.core.models.common import DocumentKind, FieldName, Model
from reimbursement_council.core.money import parse_sar_to_halalas
from reimbursement_council.core.receipt_dates import first_date, fix_digits
from reimbursement_council.core.receipt_parsing import MONEY_PATTERN
from reimbursement_council.core.text import normalize_text
from reimbursement_council.core.vision_answer import ANSWER_SCHEMA, VisionAnswer, parse_answer
from reimbursement_council.core.zatca import ZatcaInvoice

__all__ = ["ANSWER_SCHEMA", "VisionAnswer", "parse_answer"]

_TIME = re.compile(r"(\d{1,2}):(\d{2})")
NAME_FIELDS: tuple[FieldName, ...] = ("provider_name", "patient_name")
MONEY_NAMES: tuple[FieldName, ...] = ("subtotal", "vat_total", "total")


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


def one_digit_off(a: str, b: str) -> bool:
    """Same length and at most one different character: small OCR noise ("2013" for "2018")."""
    return len(a) == len(b) and sum(x != y for x, y in zip(a, b, strict=True)) <= 1


def _money_near(amount: int, printed: set[int]) -> bool:
    return any(one_digit_off(str(amount), str(p)) for p in printed)


def _date_near(day: date, printed: set[date]) -> bool:
    return any(one_digit_off(day.strftime("%Y%m%d"), p.strftime("%Y%m%d")) for p in printed)


_ARABIC_WORD = re.compile(r"[؀-ۿ]")
_LATIN_WORD = re.compile(r"[A-Za-z]")


def one_script(name: str) -> str:
    """A name printed in both scripts ("مركز الشفاء Al Shifa") keeps its Latin words, as the
    OCR parser does; a name in one script is kept as it is."""
    words = name.split()
    latin = [w for w in words if _LATIN_WORD.search(w)]
    if latin and any(_ARABIC_WORD.search(w) for w in words):
        return " ".join(latin)
    return name


# "near": printed only within one digit of OCR noise. Kept, but under the confidence floor, so
# the member is asked (1,500.00 must never quietly become 2,500.00).
Verdict = Literal["kept", "near", "made_up", "implausible", "unparsed"]


class Checked(Model):
    fields: list[ExtractedField]
    items: list[LineItem]
    kind: DocumentKind
    counts: dict[str, int]
    item_types: list[str] = []  # the model's type for each kept item, in the same order


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
        qr_money = {"total": qr.total_with_vat, "vat_total": qr.vat_total} if qr else {}
        if amount == qr_money.get(name) or amount in evidence.money:
            return "kept", str(amount)
        return ("near" if _money_near(amount, evidence.money) else "made_up"), str(amount)
    if name == "treatment_date":
        found = first_date(fix_digits(raw)[0], years)
        if found is None:
            return "unparsed", None
        day = found[0]
        if day > uploaded + timedelta(days=cfg.future_days):
            return "implausible", None
        offset = settings.policy.local_utc_offset_hours
        qr_day = None if qr is None else local_date_from_text(qr.timestamp, offset)
        if day == qr_day or day in evidence.dates:
            return "kept", day.isoformat()
        return ("near" if _date_near(day, evidence.dates) else "made_up"), day.isoformat()
    if name == "vat_number":
        digits = "".join(c for c in fix_digits(raw)[0] if c.isdigit())
        if not re.fullmatch(cfg.vat_number_pattern, digits):
            return "implausible", None
        printed = _digits_printed(digits, evidence.digits) or (
            qr is not None and qr.vat_number == digits
        )
        return ("kept" if printed else "made_up"), digits
    value = one_script(raw.strip())
    if not value:
        return "unparsed", None
    on_qr = qr is not None and name == "provider_name" and qr.seller_name.strip() == value
    printed = on_qr or name_is_printed(value, evidence.text, cfg.ground_ratio)
    return ("kept" if printed else "made_up"), value


def _qr_truth(qr: ZatcaInvoice | None, offset_hours: int) -> dict[FieldName, str]:
    if qr is None:
        return {}
    day = local_date_from_text(qr.timestamp, offset_hours)
    return {
        "total": str(qr.total_with_vat),
        "treatment_date": day.isoformat() if day else qr.timestamp[:10],
        "vat_number": qr.vat_number,
    }


def _differs_from_qr(
    name: FieldName, value: str, qr: ZatcaInvoice | None, offset_hours: int
) -> bool:
    truth = _qr_truth(qr, offset_hours).get(name)
    return truth is not None and value != truth


def _items(
    answer: VisionAnswer, evidence: Evidence, settings: Settings
) -> tuple[list[LineItem], list[str], Counter[str]]:
    counts: Counter[str] = Counter()
    items: list[LineItem] = []
    types: list[str] = []
    for item in answer.items:
        counts["items_returned"] += 1
        amount = None if item.amount is None else money_value(item.amount)
        described = name_is_printed(
            item.description, evidence.text, settings.decision.vision.ground_ratio
        )
        printed = amount is not None and amount in evidence.money
        if amount is None or amount <= 0 or not printed or not described:
            counts["items_made_up"] += 1
            continue
        first_number = re.search(r"\d+", fix_digits(item.quantity or "1")[0])
        quantity = max(1, int(first_number.group(0))) if first_number else 1
        unit = amount // quantity if amount % quantity == 0 else amount
        types.append(item.item_type)
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
    return items, types, counts


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
        if verdict not in ("kept", "near") or normalized is None:
            continue
        offset = settings.policy.local_utc_offset_hours
        if name in _qr_truth(evidence.qr, offset):
            counts["qr_compared"] += 1
        if _differs_from_qr(name, normalized, evidence.qr, offset):
            counts["qr_mismatch"] += 1  # check 3: the QR is the truth, the model value goes
            continue
        kept[name] = normalized
        cfg = settings.decision.vision
        fields.append(
            ExtractedField(
                document_id=document_id,
                name=name,
                value=normalized,
                original_text=value,
                source="vision",
                confidence=cfg.field_confidence if verdict == "kept" else cfg.disagree_confidence,
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
    items, item_types, item_counts = _items(answer, evidence, settings)
    counts.update(item_counts)
    return Checked(
        fields=fields,
        items=items,
        kind=answer.document_kind,
        counts=dict(counts),
        item_types=item_types,
    )
