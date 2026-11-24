import pytest

from reimbursement_council.synthetic.metrics import RunRow, expected_calibration_error, metrics


def row(
    lane: str,
    should_pay: bool,
    payout: int | None,
    correct: int,
    p_good: float = 0.9,
    hard_rule_failed: bool = False,
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
        hard_rule_failed=hard_rule_failed,
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
    # 65.25 SAR paid short, 155.25 SAR not paid on the false reject, one review at 25 SAR.
    assert result["total_cost_sar"] == pytest.approx(65.25 + 155.25 + 25.0)


def test_paying_a_claim_that_should_not_be_paid_costs_the_whole_payout() -> None:
    result = metrics(
        [row("auto_approve", False, 20000, 0)], reviewer_time_value=2500, tolerance=100
    )
    assert result["auto_approve_precision"] == 0.0 and result["total_cost_sar"] == 200.0


def test_ece_is_zero_when_probabilities_match_outcomes() -> None:
    assert expected_calibration_error([1.0, 0.0, 1.0], [1, 0, 1]) == 0.0
    assert expected_calibration_error([0.9, 0.9], [0, 0]) == pytest.approx(0.9)


def test_a_false_reject_costs_the_payout_that_should_have_been_made() -> None:
    result = metrics(
        [row("auto_reject", True, None, 15525)], reviewer_time_value=2500, tolerance=100
    )
    assert result["total_cost_sar"] == 155.25


def test_ece_leaves_out_claims_a_hard_rule_rejected() -> None:
    # The council never sees the hard rules, so a late claim can score 0.95 and still be
    # rejected. That is not a calibration error of the council score.
    rejected = [row("auto_reject", False, None, 0, p_good=0.95, hard_rule_failed=True)] * 5
    clean = [row("auto_approve", True, 15525, 15525, p_good=0.95)] * 5
    result = metrics(rejected + clean, reviewer_time_value=2500, tolerance=100)
    assert result["ece"] == pytest.approx(0.05)


def test_an_empty_run_is_an_error_not_zeros() -> None:
    with pytest.raises(ValueError, match="no claims"):
        metrics([], reviewer_time_value=2500, tolerance=100)


def test_ece_refuses_lists_of_different_length() -> None:
    with pytest.raises(ValueError, match="same length"):
        expected_calibration_error([0.5, 0.5], [1])
