"""Hide personal data in text that leaves the claim, such as log lines. Pure.

Masked: long numbers (VAT, ID, phone and card numbers), email addresses, and Arabic text (on
our documents that is mostly names). Kept: claim and member ids (UUIDs), amounts in halalas
(up to 8 digits) and dates, so logs stay useful for finding a problem.
"""

import re

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_LONG_NUMBER = re.compile(r"(?<![\w-])\+?\d{9,}(?![\w-])")
_ARABIC_TEXT = re.compile(r"[\u0600-\u06ff]+(?:\s+[\u0600-\u06ff]+)*")


def mask_personal_data(text: str) -> str:
    text = _EMAIL.sub("[email]", text)
    text = _LONG_NUMBER.sub("[number]", text)
    return _ARABIC_TEXT.sub("[arabic text]", text)
