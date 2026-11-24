"""Hide personal data in text that leaves the claim, such as log lines. Pure.

Masked: long numbers (VAT, ID, phone and card numbers), email addresses, and Arabic text (on
our documents that is mostly names). Kept: claim and member ids (UUIDs), amounts in halalas
(up to 8 digits) and dates, so logs stay useful for finding a problem.
"""

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_LONG_NUMBER = re.compile(r"(?<![\w-])\+?\d{9,}(?![\w-])")
_ARABIC_TEXT = re.compile(r"[\u0600-\u06ff]+(?:\s+[\u0600-\u06ff]+)*")
_SAUDI_MOBILE = re.compile(r"(?<![\w-])(?:\+966|00966|0)\s?5\d(?:[ -]?\d){7}(?![\w-])")
_IBAN = re.compile(r"\bSA\d{2}(?:\s?[0-9A-Z]{4}){5}\b")
_CARD = re.compile(r"(?<![\w-])\d{4}(?:[ -]\d{4}){3}(?![\w-])")


def mask_personal_data(text: str) -> str:
    text = _EMAIL.sub("[email]", text)
    text = _IBAN.sub("[number]", text)
    text = _CARD.sub("[number]", text)
    text = _SAUDI_MOBILE.sub("[number]", text)
    text = _LONG_NUMBER.sub("[number]", text)
    return _ARABIC_TEXT.sub("[arabic text]", text)
