"""Score a pipeline run on a synthetic set against the known right answers.

The metric names are the ones in docs/EXPERIMENTS.md.
"""

from collections.abc import Sequence

from reimbursement_council.core.models.common import Halalas, Lane, Model, Outcome, Score

AUTOMATED: frozenset[str] = frozenset({"auto_approve", "auto_reject"})
ECE_BINS = 10


class RunRow(Model):
    name: str
    lane: Lane
    outcome: Outcome
    payout_calculated: Halalas | None
    p_good: Score
    combined_score: Score
    should_pay: bool
    correct_payout: Halalas
    defects: list[str]


def paid_right(row: RunRow, tolerance: int) -> bool:
    """We should pay it, and the calculated payout is within tolerance of the right one."""
    return (
        row.should_pay
        and row.payout_calculated is not None
        and abs(row.payout_calculated - row.correct_payout) <= tolerance
    )


def expected_calibration_error(probabilities: Sequence[float], labels: Sequence[int]) -> float:
    """Average gap between predicted and actual rate, over 10 equal-width bins, weighted by size."""
    if not probabilities:
        return 0.0
    total = 0.0
    for b in range(ECE_BINS):
        low, high = b / ECE_BINS, (b + 1) / ECE_BINS
        members = [
            i
            for i, p in enumerate(probabilities)
            if low <= p < high or (b == ECE_BINS - 1 and p == 1.0)
        ]
        if members:
            predicted = sum(probabilities[i] for i in members) / len(members)
            actual = sum(labels[i] for i in members) / len(members)
            total += len(members) / len(probabilities) * abs(predicted - actual)
    return round(total, 4)


def _share(part: int, whole: int) -> float:
    return round(part / whole, 4) if whole else 0.0


def metrics(rows: Sequence[RunRow], reviewer_time_value: int, tolerance: int) -> dict[str, float]:
    approved = [r for r in rows if r.lane == "auto_approve"]
    payable = [r for r in rows if r.should_pay]
    unpayable = [r for r in rows if not r.should_pay]
    reviews = sum(r.lane == "human_review" for r in rows)
    wrong_money = 0
    for r in approved:
        if r.should_pay:
            if not paid_right(r, tolerance):
                wrong_money += abs((r.payout_calculated or 0) - r.correct_payout)
        else:
            wrong_money += r.payout_calculated or 0
    labels = [1 if paid_right(r, tolerance) else 0 for r in rows]
    return {
        "claims": len(rows),
        "automation_rate": _share(sum(r.lane in AUTOMATED for r in rows), len(rows)),
        "auto_approve_precision": _share(
            sum(paid_right(r, tolerance) for r in approved), len(approved)
        ),
        "payable_recall": _share(sum(r.lane == "auto_approve" for r in payable), len(payable)),
        "false_reject_rate": _share(sum(r.lane == "auto_reject" for r in payable), len(payable)),
        "correct_reject_rate": _share(
            sum(r.lane == "auto_reject" for r in unpayable), len(unpayable)
        ),
        "reviews_per_1000": round(1000 * reviews / len(rows), 1) if rows else 0.0,
        "self_fix_per_1000": round(1000 * sum(r.lane == "self_fix" for r in rows) / len(rows), 1)
        if rows
        else 0.0,
        "ece": expected_calibration_error([r.p_good for r in rows], labels),
        "total_cost_sar": round((wrong_money + reviews * reviewer_time_value) / 100, 2),
    }
