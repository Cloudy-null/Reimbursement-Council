"""How much a reading is worth, to pick the right way up of a turned photo. Pure."""

from reimbursement_council.core.models.claim import ReaderOutput


def reading_strength(output: ReaderOutput, floor: float) -> int:
    """Fields read at or above the confidence floor, plus line items: a photo read the right way
    up gives more of both than the same photo on its side."""
    sure = sum(1 for field in output.fields if field.confidence >= floor)
    return sure + len(output.line_items)
