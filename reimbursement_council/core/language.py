"""Is a document in a language we do not read? Pure.

We read Arabic and English. A document in another language needs a translation (source: Bupa
Arabia claim form). Urdu uses the Arabic script, so it is found by the letters Arabic does not
have; French uses the Latin script, so it is found by its common words.
"""

from collections.abc import Sequence

from reimbursement_council.config.models import UnsupportedLanguageConfig
from reimbursement_council.core.text import normalize_text


def unsupported_language(
    text_lines: Sequence[str], config: UnsupportedLanguageConfig
) -> str | None:
    """The name of the unsupported language the text is in, or None."""
    text = " ".join(text_lines)
    letters = sum(text.count(letter) for letter in config.urdu_letters)
    words = set(normalize_text(text).split())
    if letters >= config.min_urdu_letters:
        return "urdu"
    # OCR with an Arabic model turns Urdu-only letters into Arabic ones, so Urdu words that
    # Arabic does not use are the second sign (core day 4b: 0 of 6 Urdu receipts were found).
    urdu = sum(1 for word in config.urdu_words if normalize_text(word) in words)
    if urdu >= config.min_urdu_words:
        return "urdu"
    french = sum(1 for word in config.french_words if word in words)
    if french >= config.min_french_words:
        return "french"
    return None


def is_unsupported_language(text_lines: Sequence[str], config: UnsupportedLanguageConfig) -> bool:
    return unsupported_language(text_lines, config) is not None
