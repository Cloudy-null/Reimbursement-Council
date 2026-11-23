"""Money: parse SAR text into integer halalas, format it back, apply rates without floats."""

import re
from decimal import ROUND_HALF_UP, Decimal

HALALAS_PER_SAR = 100

_ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩"
_PERSIAN = "۰۱۲۳۴۵۶۷۸۹"
_TRANSLATE = {ord(char): str(index) for index, char in enumerate(_ARABIC_INDIC)}
_TRANSLATE |= {ord(char): str(index) for index, char in enumerate(_PERSIAN)}
_TRANSLATE |= {ord("٫"): ".", ord("٬"): ","}
_CURRENCY_TOKENS = ("SAR", "ر.س", "﷼")
_AMOUNT = re.compile(r"(\d+|\d{1,3}(,\d{3})+)(\.\d{1,2})?", re.ASCII)
"""Plain digits, or thousands grouped in threes ("1,150.50"). "12,50" is unclear, so None."""


def parse_sar_to_halalas(text: str) -> int | None:
    """'1,150.50 SAR' or '١٬١٥٠٫٥٠' to 115050. Anything unclear gives None, never a guess."""
    cleaned = text.translate(_TRANSLATE)
    for token in _CURRENCY_TOKENS:
        cleaned = cleaned.replace(token, "")
    cleaned = "".join(cleaned.split())
    if not _AMOUNT.fullmatch(cleaned):
        return None
    return int(Decimal(cleaned.replace(",", "")) * HALALAS_PER_SAR)


def format_sar(halalas: int) -> str:
    """15525 to '155.25'."""
    if halalas < 0:
        raise ValueError(f"money is never negative, got {halalas}")
    return f"{halalas // HALALAS_PER_SAR}.{halalas % HALALAS_PER_SAR:02d}"


def apply_rate(halalas: int, rate: float) -> int:
    """halalas times a rate (co-pay, VAT), rounded half up to whole halalas."""
    exact = Decimal(halalas) * Decimal(str(rate))
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP))
