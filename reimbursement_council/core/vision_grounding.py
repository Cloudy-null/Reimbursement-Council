"""Finding a value the model read on the page itself (the OCR text or the QR code). Pure.

Split from core/vision_checks.py (web/final). Small OCR noise is allowed: one digit off, a name
spelled a little differently, and Arabic-Indic numbers whose digits OCR scrambled.
"""

import re
from collections import Counter
from collections.abc import Sequence
from datetime import date
from difflib import SequenceMatcher

from reimbursement_council.core.models.common import Model
from reimbursement_council.core.money import parse_sar_to_halalas
from reimbursement_council.core.receipt_dates import first_date, fix_digits
from reimbursement_council.core.receipt_parsing import MONEY_PATTERN
from reimbursement_council.core.text import digits_to_ascii, normalize_text
from reimbursement_council.core.zatca import ZatcaInvoice


class Evidence(Model):
    """What the OCR and the QR code show on the same document."""

    text: str
    raw: str
    rows: list[str] = []  # each OCR row, normalized
    # Numbers printed in Arabic-Indic digits, as Western digits only (web/final): OCR often
    # scrambles their order or reads a slash as a zero, so they are compared as sets of digits.
    indic_numbers: list[str] = []
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
        rows=[normalize_text(row) for row in rows],
        indic_numbers=[
            "".join(c for c in digits_to_ascii(token) if c.isdigit())
            for line in text_lines
            for token in _INDIC_NUMBER.findall(line)
        ],
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


def digits_printed(digits: str, all_digits: str) -> bool:
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


def money_near(amount: int, printed: set[int]) -> bool:
    return any(one_digit_off(str(amount), str(p)) for p in printed)


def date_near(day: date, printed: set[date]) -> bool:
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
_INDIC_NUMBER = re.compile(r"[٠-٩][٠-٩٫٬.,/:\-]*")
_EXTRA_DIGITS = 2


def indic_digits(value_digits: str, evidence: Evidence) -> bool:
    """The value's digits all appear in one Arabic-Indic number on the page, with at most two
    extra (a slash read as a zero), in any order. Kept under the floor: the member confirms."""
    want = Counter(value_digits)
    for number in evidence.indic_numbers:
        have = Counter(number)
        extra = len(number) - len(value_digits)
        if 0 <= extra <= _EXTRA_DIGITS and not want - have:
            return True
    return False


def on_a_staff_row(value: str, rows: Sequence[str], staff_words: Sequence[str]) -> bool:
    """The name is printed on a row labeled as staff (salesperson, cashier, pharmacist)."""
    target = normalize_text(value)
    labels = [normalize_text(word) for word in staff_words]
    return bool(target) and any(
        target in row and any(label in row for label in labels) for row in rows
    )
