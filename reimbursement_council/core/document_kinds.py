"""Find a document's type from the text the reader found and whether it has a ZATCA QR.

Keywords come from config/documents.yaml, in English and Arabic. They are matched word by word
with a similarity ratio, so small OCR misreads ("REP0RT") still count but a keyword hidden
inside a longer word ("rx" in "Marx") does not. Pure logic, no I/O.
"""

from collections.abc import Sequence
from difflib import SequenceMatcher

from reimbursement_council.config.models import DocumentsConfig
from reimbursement_council.core.models.common import DocumentKind
from reimbursement_council.core.text import normalize_text

TIE_ORDER: tuple[DocumentKind, ...] = ("invoice", "receipt", "prescription", "medical_report")
"""When two kinds match equally well, the earlier one wins."""


def _keyword_score(lines: Sequence[list[str]], keyword: str, ratio: float) -> float:
    """Best similarity of the keyword against any run of the same number of words, or 0."""
    target_words = normalize_text(keyword).split()
    if not target_words:
        return 0.0
    target = " ".join(target_words)
    size = len(target_words)
    best = 0.0
    for words in lines:
        for start in range(0, len(words) - size + 1):
            window = " ".join(words[start : start + size])
            score = 1.0 if window == target else SequenceMatcher(None, window, target).ratio()
            if score >= ratio:
                best = max(best, score)
    return best


def _kind_scores(lines: Sequence[list[str]], config: DocumentsConfig) -> dict[DocumentKind, float]:
    return {
        kind: max(
            (_keyword_score(lines, word, config.kind_match_ratio) for word in keywords),
            default=0.0,
        )
        for kind, keywords in config.kind_keywords.items()
    }


def detect_kind(
    text_lines: Sequence[str], qr_payloads: Sequence[str], config: DocumentsConfig
) -> DocumentKind:
    """A QR means a billing document (an invoice when an invoice keyword is found, else a
    receipt). Without a QR, the kind with the best keyword match wins; no match is "other"."""
    lines = [normalize_text(line).split() for line in text_lines]
    scores = _kind_scores(lines, config)
    if qr_payloads:
        return "invoice" if scores.get("invoice", 0.0) > 0 else "receipt"
    ranked = [kind for kind in TIE_ORDER if scores.get(kind, 0.0) > 0]
    if not ranked:
        return "other"
    return max(ranked, key=lambda kind: (scores[kind], -TIE_ORDER.index(kind)))


def kind_with_hint(
    detected: DocumentKind, hint: DocumentKind | None, has_text: bool
) -> DocumentKind:
    """The local model's type is used only when our keywords and QR found nothing ("other") and
    the document has printed text: an Arabic report our keywords miss. A blank page stays
    "other", and the model never overrules a keyword or QR match."""
    if detected == "other" and hint is not None and has_text:
        return hint
    return detected
