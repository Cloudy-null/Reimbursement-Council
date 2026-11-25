"""Take the AI case reviewer into account so that it can only send a claim to a person.

The guarantee, by construction:
- combined score and p_good are the lower of the council with and without the reviewer, and
  disagreement the higher, so the reviewer never raises a score and never calms a dispute;
- the lane is the lane the council picks without the reviewer, except that an auto_approve can
  become human_review. Any other lane (auto_reject, self_fix, human_review) stays exactly as it
  was, so the reviewer cannot approve, cannot reject, and cannot undo a hard rule.
"""

from collections.abc import Callable, Sequence

from reimbursement_council.config.models import Settings
from reimbursement_council.core.decision.combine import combine_votes, p_good_from_score
from reimbursement_council.core.decision.lanes import LaneChoice
from reimbursement_council.core.models.common import Model, Score
from reimbursement_council.core.models.decision import Vote

DecideLane = Callable[[float, float], LaneChoice]
"""(p_good, disagreement) -> the lane, with everything else about the claim fixed."""


class GuardedDecision(Model):
    combined_score: Score
    p_good: Score
    disagreement: Score
    choice: LaneChoice
    changed_lane: bool
    effect: str


def _reasons_for_a_person(
    reviewer: Vote, council_score: float, recheck: LaneChoice, settings: Settings
) -> list[str]:
    config = settings.decision.members.case_reviewer
    reasons: list[str] = []
    if reviewer.score < config.score_floor:
        reasons.append(
            f"its score {reviewer.score:.2f} is below the floor {config.score_floor:.2f}"
        )
    gap = council_score - reviewer.score
    if gap > config.disagreement_gap:
        reasons.append(
            f"it disagrees with the other members by {gap:.2f} "
            f"(limit {config.disagreement_gap:.2f})"
        )
    if recheck.lane != "auto_approve":
        reasons.append(f"with its score the claim is not safe to approve: {recheck.reason}")
    return reasons


def apply_reviewer(
    votes: Sequence[Vote],
    reviewer: Vote | None,
    decide: DecideLane,
    settings: Settings,
) -> GuardedDecision:
    """votes: the council without the reviewer. reviewer: a used review's vote, or None."""
    council_score, council_disagreement = combine_votes(votes)
    council_p_good = p_good_from_score(council_score, settings)
    baseline = decide(council_p_good, council_disagreement)
    if reviewer is None:
        return GuardedDecision(
            combined_score=council_score,
            p_good=council_p_good,
            disagreement=council_disagreement,
            choice=baseline,
            changed_lane=False,
            effect="",
        )

    with_score, with_disagreement = combine_votes([*votes, reviewer])
    combined = min(council_score, with_score)
    p_good = min(council_p_good, p_good_from_score(with_score, settings))
    disagreement = min(1.0, max(council_disagreement, with_disagreement))
    if baseline.lane != "auto_approve":
        return GuardedDecision(
            combined_score=combined,
            p_good=p_good,
            disagreement=disagreement,
            choice=baseline,
            changed_lane=False,
            effect=f"No change: the council lane {baseline.lane} stays.",
        )

    recheck = decide(p_good, disagreement)
    reasons = _reasons_for_a_person(reviewer, council_score, recheck, settings)
    if not reasons and recheck.lane == "auto_approve":
        return GuardedDecision(
            combined_score=combined,
            p_good=p_good,
            disagreement=disagreement,
            choice=recheck,
            changed_lane=False,
            effect="No change: the reviewer agrees the claim is safe to approve.",
        )
    reason = "The AI case reviewer asked for a person: " + "; ".join(reasons) + "."
    return GuardedDecision(
        combined_score=combined,
        p_good=p_good,
        disagreement=disagreement,
        choice=LaneChoice(lane="human_review", outcome="queued", reason=reason, request=None),
        changed_lane=True,
        effect=reason,
    )
