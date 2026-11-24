"""Combine council votes: weighted mean score and weighted spread (disagreement)."""

import math
from collections.abc import Sequence

from reimbursement_council.config.models import Settings
from reimbursement_council.core.decision.calibration import apply_platt
from reimbursement_council.core.models.decision import Vote


def combine_votes(votes: Sequence[Vote]) -> tuple[float, float]:
    """(combined score, disagreement). Disagreement is the weighted standard deviation."""
    total_weight = sum(vote.weight for vote in votes)
    if total_weight <= 0:
        raise ValueError("council votes have no weight to combine")
    mean = sum(vote.weight * vote.score for vote in votes) / total_weight
    variance = sum(vote.weight * (vote.score - mean) ** 2 for vote in votes) / total_weight
    return min(1.0, max(0.0, mean)), math.sqrt(variance)


def p_good_from_score(score: float, settings: Settings) -> float:
    """Probability the claim should be paid as calculated: Platt scaling when calibration is on,
    the raw combined score when it is off."""
    if not settings.decision.calibration_enabled:
        return score
    if settings.calibration is None:
        raise ValueError("calibration is on but no fitted parameters were loaded")
    return apply_platt(score, settings.calibration)
