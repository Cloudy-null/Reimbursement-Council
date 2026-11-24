"""Score a pipeline run on a synthetic set against the known right answers.

The metric names are the ones in docs/EXPERIMENTS.md. Total cost is wrong payouts plus review
cost: paying too much, paying too little, and not paying a payable claim (a false reject) all
count. ECE and the calibration fit use only claims no hard rule rejected (decision 007): the
council does not see the hard rules, so a late claim can score high and still be right to reject.
"""

from collections.abc import Sequence

from pydantic import Field

from reimbursement_council.core.models.common import Halalas, Lane, Model, Outcome, Score

AUTOMATED: frozenset[str] = frozenset({"auto_approve", "auto_reject"})
HEAVY_DAMAGE: frozenset[str] = frozenset({"heavy", "unreadable"})
HEAVY_DAMAGE_LANES = ("self_fix", "auto_approve", "auto_reject", "human_review")
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
    hard_rule_failed: bool
    damage: str
    # Documents (Task 11). Empty for runs made before document sets.
    kinds_read: dict[str, str] = Field(default_factory=dict)
    kinds_true: dict[str, str] = Field(default_factory=dict)
    needs_flagged: list[list[str]] = Field(default_factory=list)
    needs_missing: list[list[str]] = Field(default_factory=list)
    cross_check_failed: bool = False
    cross_check_expected: bool = False
    expected_lane: Lane | None = None
    # Self-fix simulation (run-set --simulate-fix): the lane before the fixed file was sent.
    first_lane: Lane | None = None
    fix_tried: bool = False
    # The patient's past claims, for the fairness check (E9: new vs tenured members).
    past_claims: int | None = None


def paid_right(row: RunRow, tolerance: int) -> bool:
    """We should pay it, and the calculated payout is within tolerance of the right one."""
    return (
        row.should_pay
        and row.payout_calculated is not None
        and abs(row.payout_calculated - row.correct_payout) <= tolerance
    )


def expected_calibration_error(probabilities: Sequence[float], labels: Sequence[int]) -> float:
    """Average gap between predicted and actual rate, over 10 equal-width bins, weighted by size."""
    if len(probabilities) != len(labels):
        raise ValueError(
            f"probabilities and labels must be the same length: {len(probabilities)}, {len(labels)}"
        )
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


def calibration_rows(rows: Sequence[RunRow]) -> list[RunRow]:
    """The rows the council score is judged on: no hard rule rejected the claim."""
    return [r for r in rows if not r.hard_rule_failed]


def heavy_damage_metrics(rows: Sequence[RunRow], tolerance: int) -> dict[str, float]:
    """Where badly damaged photos end up. The safe lane is self_fix (ask for a new photo); an
    auto approve on a photo we could not read is the mistake that matters most."""
    damaged = [r for r in rows if r.damage in HEAVY_DAMAGE]
    result: dict[str, float] = {"heavy_damage_claims": len(damaged)}
    for lane in HEAVY_DAMAGE_LANES:
        result[f"heavy_damage_{lane}_share"] = _share(
            sum((r.first_lane or r.lane) == lane for r in damaged), len(damaged)
        )
    result["heavy_damage_wrong_auto_approves"] = sum(
        (r.first_lane or r.lane) == "auto_approve" and not paid_right(r, tolerance) for r in damaged
    )
    return result


def metrics(rows: Sequence[RunRow], reviewer_time_value: int, tolerance: int) -> dict[str, float]:
    if not rows:
        raise ValueError("no claims in the run: nothing to score")
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
    for r in rows:
        if r.lane == "auto_reject" and r.should_pay:
            wrong_money += r.correct_payout
    judged = calibration_rows(rows)
    labels = [1 if paid_right(r, tolerance) else 0 for r in judged]
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
        "ece": expected_calibration_error([r.p_good for r in judged], labels),
        "total_cost_sar": round((wrong_money + reviews * reviewer_time_value) / 100, 2),
    } | heavy_damage_metrics(rows, tolerance)


def self_fix_metrics(rows: Sequence[RunRow], tolerance: int) -> dict[str, float]:
    """For runs with --simulate-fix: of the claims where the member sent the fixed file, the
    share that were then paid right with no person (success), and the share that went to a
    person. Without the simulation the counts are 0."""
    tried = [r for r in rows if r.fix_tried]
    success = sum(r.lane == "auto_approve" and paid_right(r, tolerance) for r in tried)
    return {
        "self_fix_tried": len(tried),
        "self_fix_success_rate": _share(success, len(tried)),
        "self_fix_to_human_rate": _share(sum(r.lane == "human_review" for r in tried), len(tried)),
    }


def fairness_metrics(rows: Sequence[RunRow], min_past_claims: int) -> dict[str, float]:
    """E9 fairness: is a payable claim from a new member (fewer past claims than the history
    member needs) rejected or sent away from auto approve more often than a tenured one's?"""
    known = [r for r in rows if r.past_claims is not None and r.should_pay]
    groups = {
        "new": [r for r in known if (r.past_claims or 0) < min_past_claims],
        "tenured": [r for r in known if (r.past_claims or 0) >= min_past_claims],
    }
    result: dict[str, float] = {}
    for name, group in groups.items():
        result[f"payable_{name}_members"] = len(group)
        result[f"false_reject_rate_{name}"] = _share(
            sum(r.lane == "auto_reject" for r in group), len(group)
        )
        result[f"payable_recall_{name}"] = _share(
            sum(r.lane == "auto_approve" for r in group), len(group)
        )
    return result
