import pytest

from reimbursement_council.core.decision.combine import combine_votes, p_good_from_score
from reimbursement_council.core.models.decision import Vote
from tests.factories import repo_settings


def votes(*scores: float, weights: tuple[float, ...] | None = None) -> list[Vote]:
    weights = weights or tuple(1.0 for _ in scores)
    return [
        Vote(member="document_checker", score=score, weight=weight, reason="r", evidence=[])
        for score, weight in zip(scores, weights, strict=True)
    ]


def test_combine_equal_weights() -> None:
    assert combine_votes(votes(1.0, 1.0, 1.0, 0.9)) == pytest.approx((0.975, 0.0433), abs=1e-4)


def test_combine_weighted() -> None:  # score 1.0 weight 3, score 0.0 weight 1
    assert combine_votes(votes(1.0, 0.0, weights=(3.0, 1.0))) == pytest.approx(
        (0.75, 0.4330), abs=1e-4
    )


def test_combine_all_agree_has_no_disagreement() -> None:
    assert combine_votes(votes(0.6, 0.6)) == pytest.approx((0.6, 0.0))


def test_combine_zero_weight_raises() -> None:
    with pytest.raises(ValueError, match="weight"):
        combine_votes(votes(1.0, 0.5, weights=(0.0, 0.0)))
    with pytest.raises(ValueError, match="weight"):
        combine_votes([])


def test_p_good_is_the_score_while_calibration_is_off() -> None:
    assert p_good_from_score(0.8, repo_settings()) == 0.8
