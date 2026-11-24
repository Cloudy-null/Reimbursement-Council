import pytest

from reimbursement_council.synthetic.metrics import RunRow, expected_calibration_error, metrics


def row(
    lane: str, should_pay: bool, payout: int | None, correct: int, p_good: float = 0.9
) -> RunRow:
    return RunRow(
        name="x",
        lane=lane,
        outcome="complete",
        payout_calculated=payout,
        p_good=p_good,
        combined_score=p_good,
        should_pay=should_pay,
        correct_payout=correct,
        defects=[],
    )


def test_metrics_on_a_small_run() -> None:
    rows = [
        row("auto_approve", True, 15525, 15525),  # paid right
        row("auto_approve", True, 9000, 15525),  # paid wrong: 65.25 SAR short
        row("auto_reject", True, None, 15525),  # false reject
        row("auto_reject", False, None, 0),  # correct reject
        row("human_review", True, 15525, 15525),
        row("self_fix", True, 15525, 15525),
    ]
    result = metrics(rows, reviewer_time_value=2500, tolerance=100)
    assert result["claims"] == 6
    assert result["automation_rate"] == pytest.approx(4 / 6, abs=1e-3)
    assert result["auto_approve_precision"] == 0.5
    assert result["payable_recall"] == pytest.approx(2 / 5, abs=1e-3)
    assert result["false_reject_rate"] == pytest.approx(1 / 5, abs=1e-3)
    assert result["reviews_per_1000"] == pytest.approx(1000 / 6, abs=0.1)
    assert result["total_cost_sar"] == pytest.approx(65.25 + 25.0)


def test_paying_a_claim_that_should_not_be_paid_costs_the_whole_payout() -> None:
    result = metrics(
        [row("auto_approve", False, 20000, 0)], reviewer_time_value=2500, tolerance=100
    )
    assert result["auto_approve_precision"] == 0.0 and result["total_cost_sar"] == 200.0


def test_ece_is_zero_when_probabilities_match_outcomes() -> None:
    assert expected_calibration_error([1.0, 0.0, 1.0], [1, 0, 1]) == 0.0
    assert expected_calibration_error([0.9, 0.9], [0, 0]) == pytest.approx(0.9)
