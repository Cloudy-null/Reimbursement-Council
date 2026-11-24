"""Text normalizing for matching receipt words in Arabic and English.

Receipts and OCR write the same word in many ways: hamza forms, taa marbuta, tatweel,
diacritics, case, punctuation. normalize_text maps them to one form so labels and service
names can be compared.
"""

import re

_ARABIC_INDIC = "٠١٢٣٤٥٦٧٨٩"
_PERSIAN = "۰۱۲۳۴۵۶۷۸۹"
_DIGITS = {ord(char): str(index) for index, char in enumerate(_ARABIC_INDIC)}
_DIGITS |= {ord(char): str(index) for index, char in enumerate(_PERSIAN)}
_DIGITS |= {ord("٫"): ".", ord("٬"): ","}

_LETTERS = {
    ord("أ"): "ا",
    ord("إ"): "ا",
    ord("آ"): "ا",
    ord("ٱ"): "ا",
    ord("ى"): "ي",
    ord("ة"): "ه",
    ord("ؤ"): "و",
    ord("ئ"): "ي",
    ord("ـ"): None,  # tatweel
}
_DIACRITICS = re.compile("[ً-ْٰ]")
_NOT_WORD = re.compile(r"[^\w]+")


def digits_to_ascii(text: str) -> str:
    return text.translate(_DIGITS)


def normalize_text(text: str) -> str:
    """Lowercase, one form per Arabic letter, no diacritics or punctuation, single spaces."""
    cleaned = _DIACRITICS.sub("", digits_to_ascii(text)).translate(_LETTERS).casefold()
    return " ".join(_NOT_WORD.sub(" ", cleaned).split())
