"""Is a name read on a document the same person as the name on the account? Pure.

web/final, to cut false patient-name alarms (0.45 of the optical set):
- Words are compared one by one after normalizing Arabic letter forms; the shorter name only
  has to be contained in the longer one ("Nasser" is in "Turki Nasser"). A leading "ال" and
  a "bin"/"بن" do not count.
- Label words left in a name ("المريض", "patient") are dropped; a "name" with digits is not one.
- An Arabic name and an English one are compared by their consonants ("محمد" and "Mohammed").
"""

import re
from difflib import SequenceMatcher

from reimbursement_council.core.text import normalize_text

LABEL_WORDS = frozenset(
    normalize_text(w)
    for w in ("المريض", "اسم", "المراجع", "العميل", "patient", "name", "customer", "mr", "mrs")
)
LINK_WORDS = frozenset(normalize_text(w) for w in ("بن", "بنت", "bin", "bint", "ibn", "al", "el"))
# Arabic letters to the Latin consonants people use for them in names (a rough guide).
_LATIN_OF = {
    "ب": "b", "ت": "t", "ث": "th", "ج": "j", "ح": "h", "خ": "kh", "د": "d", "ذ": "th",
    "ر": "r", "ز": "z", "س": "s", "ش": "sh", "ص": "s", "ض": "d", "ط": "t", "ظ": "z",
    "ع": "", "غ": "gh", "ف": "f", "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n",
    "ه": "h", "و": "w", "ي": "y", "ا": "", "ء": "",
}  # fmt: skip
_VOWELS = re.compile(r"[aeiouy]+")
_ARABIC = re.compile(r"[؀-ۿ]")


def _words(name: str) -> list[str]:
    words = []
    for word in normalize_text(name).split():
        if word in LABEL_WORDS or word in LINK_WORDS:
            continue
        if word.startswith("ال") and len(word) > 3:
            word = word[2:]
        words.append(word)
    return words


def _consonants(word: str) -> str:
    """A spelling-free key: Arabic letters to Latin, then vowels and doubled letters dropped."""
    latin = "".join(_LATIN_OF.get(ch, ch) for ch in word) if _ARABIC.search(word) else word
    latin = latin.replace("q", "k").replace("ee", "i").replace("oo", "u")
    key = _VOWELS.sub("", latin.replace("w", "").replace("h", ""))
    return re.sub(r"(.)\1+", r"\1", key)


def _word_match(a: str, b: str, ratio: float) -> bool:
    if a == b or SequenceMatcher(None, a, b).ratio() >= ratio:
        return True
    ka, kb = _consonants(a), _consonants(b)
    return bool(ka) and (ka == kb or SequenceMatcher(None, ka, kb).ratio() >= ratio)


def is_a_name(text: str) -> bool:
    return bool(_words(text)) and not any(ch.isdigit() for ch in text)


def same_person(read: str, account: str, ratio: float) -> bool:
    """Every word of the shorter name matches a different word of the longer one."""
    left, right = _words(read), _words(account)
    if not left or not right:
        return False
    joined_left, joined_right = "".join(left), "".join(right)
    if joined_left == joined_right:  # OCR dropped or added a space: "بدرفهد"
        return True
    short, long = (left, right) if len(left) <= len(right) else (right, left)
    free = list(long)
    for word in short:
        match = next((w for w in free if _word_match(word, w, ratio)), None)
        if match is None:
            return False
        free.remove(match)
    return True
