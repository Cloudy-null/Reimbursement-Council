"""Gregorian date to Hijri date, for printing Hijri dates on synthetic receipts. Pure.

This is the arithmetic (tabular) Islamic calendar. Saudi Arabia uses Umm al-Qura, which is
based on the moon and can differ by a day or two, so these dates are close but not official.
That is enough for synthetic receipts; the truth always keeps the Gregorian date.
"""

import math
from datetime import date

ISLAMIC_EPOCH = 1948439.5  # Julian day of 1 Muharram 1 AH (tabular calendar)
ORDINAL_TO_JULIAN_DAY = 1721424.5  # date.toordinal() plus this is the Julian day at midnight


def _islamic_to_julian_day(year: int, month: int, day: int) -> float:
    return (
        day
        + math.ceil(29.5 * (month - 1))
        + (year - 1) * 354
        + math.floor((3 + 11 * year) / 30)
        + ISLAMIC_EPOCH
        - 1
    )


def to_hijri(day: date) -> tuple[int, int, int]:
    """(year, month, day) in the tabular Islamic calendar."""
    julian = math.floor(day.toordinal() + ORDINAL_TO_JULIAN_DAY) + 0.5
    year = math.floor((30 * (julian - ISLAMIC_EPOCH) + 10646) / 10631)
    month = min(12, math.ceil((julian - (29 + _islamic_to_julian_day(year, 1, 1))) / 29.5) + 1)
    month = max(1, month)
    hijri_day = int(julian - _islamic_to_julian_day(year, month, 1)) + 1
    return year, month, hijri_day


def hijri_text(day: date) -> str:
    """'1448/05/04' (year/month/day), the way Saudi receipts print it before هـ."""
    year, month, hijri_day = to_hijri(day)
    return f"{year}/{month:02d}/{hijri_day:02d}"
