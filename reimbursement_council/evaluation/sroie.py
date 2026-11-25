"""Score the reader on real receipts from SROIE (ICDAR 2019, scanned receipts from Malaysia).

A key file gives the true company, date and total. Pure: the caller reads the files. The
amounts are ringgit with two decimals, which map to halalas the same way (1.00 = 100).
"""

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from difflib import SequenceMatcher

from reimbursement_council.core.models.claim import ExtractionResult
from reimbursement_council.core.models.common import Model
from reimbursement_council.core.text import normalize_text

FIELDS = ("provider_name", "treatment_date", "total")
DATE_FORMATS = (
    "%d/%m/%Y",
    "%d/%m/%y",
    "%d-%m-%Y",
    "%d-%m-%y",
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d.%m.%y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%d %b %y",
)


class RealTruth(Model):
    company: str
    date: str | None  # YYYY-MM-DD, None when the key's date has a form we do not know
    total: int | None  # in hundredths (sen, like halalas)


def _date(text: str) -> str | None:
    cleaned = " ".join(text.replace(",", ", ").split()).replace(" ,", ",")
    for form in DATE_FORMATS:
        try:
            day: date = datetime.strptime(cleaned.title(), form).date()
        except ValueError:
            continue
        return day.isoformat()
    return None


def _hundredths(text: str) -> int | None:
    digits = "".join(c for c in text if c.isdigit() or c == ".")
    if digits.count(".") != 1:
        return None
    whole, cents = digits.split(".")
    if not whole.isdigit() or len(cents) != 2 or not cents.isdigit():
        return None
    return int(whole) * 100 + int(cents)


def parse_sroie_key(key: Mapping[str, str]) -> RealTruth:
    return RealTruth(
        company=key.get("company", "").strip(),
        date=_date(key.get("date", "")),
        total=_hundredths(key.get("total", "")),
    )


def _same_company(read: str, true: str, ratio: float) -> bool:
    left, right = normalize_text(read), normalize_text(true)
    return bool(left) and (left == right or SequenceMatcher(None, left, right).ratio() >= ratio)


def compare_real(
    truth: RealTruth, reading: ExtractionResult, ratio: float
) -> dict[str, bool | None]:
    """True or False per field; None when the truth is not known for that field."""
    provider = reading.best("provider_name")
    day = reading.day("treatment_date")
    total = reading.money("total")
    return {
        "provider_name": provider is not None
        and _same_company(provider.value, truth.company, ratio),
        "treatment_date": None
        if truth.date is None
        else day is not None and day.isoformat() == truth.date,
        "total": None if truth.total is None else total == truth.total,
    }


def summarize_real(rows: Sequence[Mapping[str, bool | None]]) -> dict[str, float]:
    summary: dict[str, float] = {"receipts": len(rows)}
    for name in FIELDS:
        known = [row[name] for row in rows if row.get(name) is not None]
        summary[name] = round(sum(bool(v) for v in known) / len(known), 4) if known else 0.0
        summary[f"{name}_count"] = len(known)
    return summary
