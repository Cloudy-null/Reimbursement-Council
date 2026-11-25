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
    if letters >= config.min_urdu_letters:
        return "urdu"
    words = set(normalize_text(text).split())
    french = sum(1 for word in config.french_words if word in words)
    if french >= config.min_french_words:
        return "french"
    return None


def is_unsupported_language(text_lines: Sequence[str], config: UnsupportedLanguageConfig) -> bool:
    return unsupported_language(text_lines, config) is not None
