import random

import pytest

from reimbursement_council.core.decision.calibration import PlattParams, apply_platt, fit_platt


def test_fit_learns_a_rising_curve() -> None:
    rng = random.Random(1)
    scores = [rng.random() for _ in range(400)]
    labels = [1 if rng.random() < s**3 else 0 for s in scores]  # raw scores are overconfident
    params = fit_platt(scores, labels)
    assert params.a > 0
    assert apply_platt(0.9, params) < 0.9  # pulls the overconfident top down
    assert apply_platt(0.2, params) < apply_platt(0.9, params)


def test_apply_is_a_probability() -> None:
    params = PlattParams(a=12.0, b=-6.0)
    assert apply_platt(0.5, params) == pytest.approx(0.5)
    assert 0.0 < apply_platt(0.0, params) < apply_platt(1.0, params) < 1.0


def test_fit_needs_both_outcomes() -> None:
    with pytest.raises(ValueError, match="both"):
        fit_platt([0.2, 0.9], [1, 1])
