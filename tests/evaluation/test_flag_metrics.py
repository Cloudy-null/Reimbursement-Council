from reimbursement_council.evaluation.flag_metrics import flag_metrics
from reimbursement_council.synthetic.metrics import RunRow


def row(lane: str, should_pay: bool, defects: list[str], paid: int | None = 100) -> RunRow:
    return RunRow(
        name="c", lane=lane, outcome="complete", payout_calculated=paid, p_good=0.5,  # type: ignore[arg-type]
        combined_score=0.5, should_pay=should_pay, correct_payout=100, defects=defects,
        hard_rule_failed=False, damage="none",
    )  # fmt: skip


def test_the_four_shares_and_their_counts() -> None:
    rows = [
        row("auto_approve", True, []),  # right approval
        row("auto_approve", True, [], paid=50),  # approved at the wrong amount
        row("self_fix", True, ["blurry"]),  # problem flagged
        row("human_review", True, []),  # flagged without a problem
        row("auto_reject", False, ["late"]),  # problem flagged
    ]
    m = flag_metrics(rows, tolerance=0)
    assert m["approval_precision"] == {"value": 0.5, "hits": 1, "n": 2}
    assert m["payable_recall"] == {"value": 0.5, "hits": 2, "n": 4}
    assert m["problem_precision"] == {"value": 0.6667, "hits": 2, "n": 3}
    assert m["problem_recall"] == {"value": 1.0, "hits": 2, "n": 2}
    assert flag_metrics([], 0)["approval_precision"]["value"] is None
