"""Pick the lane for a claim. First match wins:

1. A hard rule failed on confident data: auto_reject.
2. A hard rule could not run (unclear data): self_fix, or human_review with no retries left.
3. Safe to approve: auto_approve (complete or partial).
4. Low score and a member asked for something: self_fix.
5. Everything else: human_review.

Only step 1 rejects, so no council member can reject a claim on its own.
"""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from reimbursement_council.config.models import DecisionConfig, Settings
from reimbursement_council.core.models.common import Lane, Model, Outcome
from reimbursement_council.core.models.decision import (
    PayoutResult,
    RuleResult,
    SelfFixRequest,
    Vote,
)
from reimbursement_council.core.money import format_sar


class LaneChoice(Model):
    lane: Lane
    outcome: Outcome
    reason: str
    request: SelfFixRequest | None


def expected_loss(p_good: float, payout_calculated: int) -> int:
    """(1 - p_good) x payout, in halalas, rounded half up."""
    exact = (1 - Decimal(str(p_good))) * payout_calculated
    return int(exact.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _first_vote_request(votes: Sequence[Vote]) -> SelfFixRequest | None:
    for vote in votes:
        if vote.request is not None and vote.request_kind is not None and vote.request_field:
            return SelfFixRequest(
                kind=vote.request_kind, field=vote.request_field, text=vote.request
            )
    return None


def _retries_left(retries_used: int, decision: DecisionConfig) -> bool:
    return decision.self_fix_enabled and retries_used < decision.self_fix_max_retries


def _approval(
    p_good: float, disagreement: float, payout: PayoutResult | None, decision: DecisionConfig
) -> tuple[list[str], str]:
    """(what blocks auto approve, the approve reason if nothing does)."""
    blockers: list[str] = []
    approve_reason = ""
    if payout is None:
        blockers.append("no payout could be priced")
    else:
        if payout.unmatched_items:
            blockers.append(f"items not in the price list: {', '.join(payout.unmatched_items)}")
        if (
            decision.always_review_amount_enabled
            and payout.calculated >= decision.always_review_amount_halalas
        ):
            blockers.append("the amount is at or above the always-review amount")
        if decision.cost_lanes_enabled:
            loss = expected_loss(p_good, payout.calculated)
            limit = decision.reviewer_time_value_halalas
            if loss < limit:
                approve_reason = (
                    f"Expected loss {format_sar(loss)} SAR is below the reviewer time value "
                    f"{format_sar(limit)} SAR."
                )
            else:
                blockers.append(
                    f"expected loss {format_sar(loss)} SAR is not below the reviewer time value "
                    f"{format_sar(limit)} SAR"
                )
        elif p_good >= decision.fixed_p_good_threshold:
            threshold = decision.fixed_p_good_threshold
            approve_reason = f"p_good {p_good:.2f} meets the fixed threshold {threshold:.2f}."
        else:
            blockers.append(
                f"p_good {p_good:.2f} is below the fixed threshold "
                f"{decision.fixed_p_good_threshold:.2f}"
            )
    limit_text = f"{decision.disagreement_limit:.2f}"
    if decision.disagreement_routing_enabled and disagreement >= decision.disagreement_limit:
        blockers.append(f"disagreement {disagreement:.2f} is not below the limit {limit_text}")
    return blockers, approve_reason


def choose_lane(
    rule_results: Sequence[RuleResult],
    votes: Sequence[Vote],
    p_good: float,
    disagreement: float,
    payout: PayoutResult | None,
    retries_used: int,
    settings: Settings,
    extra_blockers: Sequence[str] = (),
) -> LaneChoice:
    """extra_blockers: data problems from approval_blockers that stop auto approve."""
    decision = settings.decision
    failed = [result for result in rule_results if result.outcome == "fail"]
    if failed:
        first = failed[0]
        return LaneChoice(
            lane="auto_reject",
            outcome="complete",
            reason=f"Hard rule failed: {first.rule}. {first.reason}",
            request=None,
        )

    unsure = [result for result in rule_results if result.outcome == "not_sure"]
    if unsure:
        first = unsure[0]
        if not _retries_left(retries_used, decision):
            return LaneChoice(
                lane="human_review",
                outcome="queued",
                reason=f"Hard rule {first.rule} could not run on unclear data, no retries left.",
                request=None,
            )
        field = first.fields[0] if first.fields else first.rule
        request = _first_vote_request(votes) or SelfFixRequest(
            kind="confirm_field", field=field, text=f"Please confirm the {field}."
        )
        return LaneChoice(
            lane="self_fix",
            outcome="queued",
            reason=f"Hard rule {first.rule} could not run on unclear data. Asking the member.",
            request=request,
        )

    blockers, approve_reason = _approval(p_good, disagreement, payout, decision)
    blockers = list(extra_blockers) + blockers
    if not blockers and payout is not None:
        return LaneChoice(
            lane="auto_approve",
            outcome="partial" if payout.is_partial else "complete",
            reason=approve_reason,
            request=None,
        )

    vote_request = _first_vote_request(votes)
    if (
        p_good < decision.self_fix_p_good_limit
        and vote_request is not None
        and _retries_left(retries_used, decision)
    ):
        return LaneChoice(
            lane="self_fix",
            outcome="queued",
            reason=f"Score {p_good:.2f} is low and the member can fix the {vote_request.field}.",
            request=vote_request,
        )
    return LaneChoice(
        lane="human_review",
        outcome="queued",
        reason="Not auto approved: " + "; ".join(blockers) + ".",
        request=None,
    )
