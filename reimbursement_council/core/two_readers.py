"""Two readers on one document: the local model and EasyOCR (switch two_readers_enabled).

When both read a field and agree, it gets agree_confidence. When they disagree, the model's
value is kept with disagree_confidence (under the floor), so the member is asked to check it.
A field only one reader found keeps that reader's own confidence. Pure logic, no I/O.
"""

from collections import Counter
from difflib import SequenceMatcher

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import ExtractedField
from reimbursement_council.core.text import normalize_text
from reimbursement_council.core.vision_checks import NAME_FIELDS


def same_value(name: str, a: str, b: str, ratio: float) -> bool:
    if name in NAME_FIELDS:
        x, y = normalize_text(a), normalize_text(b)
        return x == y or SequenceMatcher(None, x, y).ratio() >= ratio
    return a == b


def merge_readers(
    vision: list[ExtractedField], ocr: list[ExtractedField], settings: Settings
) -> tuple[list[ExtractedField], dict[str, int]]:
    cfg = settings.decision.vision
    counts: Counter[str] = Counter()
    ocr_by_name: dict[str, ExtractedField] = {}
    for field in ocr:  # the most confident OCR value of each name
        best = ocr_by_name.get(field.name)
        if best is None or field.confidence > best.confidence:
            ocr_by_name[field.name] = field
    merged: list[ExtractedField] = []
    for field in vision:
        other = ocr_by_name.pop(field.name, None)
        if other is None:
            merged.append(field)
            continue
        if same_value(field.name, field.value, other.value, cfg.ground_ratio):
            counts["readers_agree"] += 1
            merged.append(field.model_copy(update={"confidence": cfg.agree_confidence}))
        else:
            counts["readers_disagree"] += 1
            note = f"{field.original_text} (EasyOCR read {other.value})"
            merged.append(
                field.model_copy(
                    update={"confidence": cfg.disagree_confidence, "original_text": note}
                )
            )
    merged.extend(ocr_by_name.values())
    return merged, dict(counts)
