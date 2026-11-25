"""Dates on receipts: find the treatment date (and time) in a row of OCR text, and how sure we
are of it. Pure logic, no I/O. Split from receipt_parsing.py (core day 4)."""

import re
from datetime import date

from reimbursement_council.core.models.common import FieldName
from reimbursement_council.core.receipt_rows import OcrLine
from reimbursement_council.core.text import digits_to_ascii

_DATE_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:\s+(\d{1,2}):(\d{2}))?")
# Day first: 08/11/2026, 29-12-2017, 5.6.2018, and two digit years 12/03/18 (found on real
# receipts, E1 failure review). A dot with a two digit year is left out: it looks like a time.
_DATE_DMY = re.compile(
    r"(?<!\d)(\d{1,2})([/.-])(\d{1,2})\2(\d{4}|\d{2})(?!\d)(?!\.\d)(?:\s+(\d{1,2}):(\d{2}))?"
)
_TIME = re.compile(r"(?<!\d)\d{1,2}\s?:\s?\d{2}(?!\d)")
_DATE_WORD = re.compile(r"date|تاريخ", re.IGNORECASE)
_DIGITISH = re.compile(r"[0-9OoIl]{2,}")


def fix_digits(text: str) -> tuple[str, bool]:
    """Letter O, I or l inside a number becomes 0 or 1. Returns the text and whether it changed."""

    def fix(match: re.Match[str]) -> str:
        token = match.group(0)
        if not any(char.isdigit() for char in token):
            return token
        return token.replace("O", "0").replace("o", "0").replace("I", "1").replace("l", "1")

    fixed = _DIGITISH.sub(fix, digits_to_ascii(text))
    return fixed, fixed != digits_to_ascii(text)


def first_date(text: str, years: tuple[int, int]) -> tuple[date, str | None, str | None] | None:
    """The date in the text, with the time after it if there is one. A YYYY-MM-DD date wins over
    a day-first one (a receipt may print the Hijri date first). Only real calendar dates in the
    year range count. A two digit year counts with slashes (12/03/18), or with dashes or dots
    when the row also has a time or the word date (17-03-18 14:49): a code like "Ref 10-10-10"
    has neither."""
    stamped = bool(_TIME.search(text) or _DATE_WORD.search(text))
    candidates: list[tuple[int, int, str, str, str, str | None, str | None]] = []
    for match in _DATE_ISO.finditer(text):
        year, month, day, hour, minute = match.groups()
        candidates.append((0, match.start(), year, month, day, hour, minute))
    for match in _DATE_DMY.finditer(text):
        day, sep, month, year, hour, minute = match.groups()
        if len(year) == 2 and sep != "/" and not stamped:
            continue
        full_year = f"20{year}" if len(year) == 2 else year
        candidates.append((1, match.start(), full_year, month, day, hour, minute))
    for _, _, year, month, day, hour, minute in sorted(candidates):
        if not years[0] <= int(year) <= years[1]:
            continue
        try:
            return date(int(year), int(month), int(day)), hour, minute
        except ValueError:
            continue
    return None


_DATE_PART = re.compile(r"\d{1,4}\s*[/.\-]\s*\d{1,2}|\d{1,2}:\d{2}")


def date_confidence(row: list[OcrLine]) -> float:
    """Confidence per field: the boxes that hold the date (and its time), not a label such as
    "Date:" beside it. A misread label used to pull a right date under the floor."""
    fixed = [(fix_digits(x.text)[0], x) for x in row]
    parts = [x for text, x in fixed if _DATE_PART.search(text)]
    digits = [x for text, x in fixed if any(c.isdigit() for c in text)]
    return min(x.confidence for x in (parts or digits or row))


def date_values(row_text: str, years: tuple[int, int]) -> list[tuple[FieldName, str]]:
    """The treatment date in the row as YYYY-MM-DD, and the invoice time stamp when a time
    follows it. Empty when the row has no date."""
    text, _ = fix_digits(row_text)
    found = first_date(text, years)
    if found is None:
        return []
    day_value, hour, minute = found
    date_text = day_value.isoformat()
    values: list[tuple[FieldName, str]] = [("treatment_date", date_text)]
    if hour and minute:
        values.append(("invoice_timestamp", f"{date_text}T{int(hour):02d}:{minute}:00"))
    return values
