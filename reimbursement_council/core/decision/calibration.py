"""Platt scaling: turn the council's combined score into a probability the claim is paid right.

p_good = 1 / (1 + exp(-(a * score + b))), with a and b fitted on the labeled tune set by Newton
steps on the log loss. Targets use Platt's smoothing, (positives + 1) / (positives + 2) and
1 / (negatives + 2), so a small set does not give probabilities of exactly 0 or 1.
"""

import math
from collections.abc import Sequence

from reimbursement_council.core.models.common import Model

NEWTON_STEPS = 100
RIDGE = 1e-9  # keeps the 2 by 2 system solvable when the scores barely vary


class PlattParams(Model):
    a: float
    b: float


def apply_platt(score: float, params: PlattParams) -> float:
    z = params.a * score + params.b
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    exp_z = math.exp(z)
    return exp_z / (1.0 + exp_z)


def fit_platt(scores: Sequence[float], labels: Sequence[int]) -> PlattParams:
    positives = sum(1 for y in labels if y)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        raise ValueError("calibration needs both paid-right and not-paid-right examples")
    high = (positives + 1) / (positives + 2)
    low = 1 / (negatives + 2)
    targets = [high if y else low for y in labels]
    a, b = 0.0, math.log((negatives + 1) / (positives + 1)) * -1
    for _ in range(NEWTON_STEPS):
        g_a = g_b = h_aa = h_ab = h_bb = 0.0
        for s, t in zip(scores, targets, strict=True):
            p = apply_platt(s, PlattParams(a=a, b=b))
            d = p - t
            w = p * (1 - p)
            g_a += d * s
            g_b += d
            h_aa += w * s * s
            h_ab += w * s
            h_bb += w
        h_aa += RIDGE
        h_bb += RIDGE
        det = h_aa * h_bb - h_ab * h_ab
        if det <= 0:
            break
        step_a = (h_bb * g_a - h_ab * g_b) / det
        step_b = (h_aa * g_b - h_ab * g_a) / det
        a, b = a - step_a, b - step_b
        if abs(step_a) < 1e-9 and abs(step_b) < 1e-9:
            break
    return PlattParams(a=a, b=b)
