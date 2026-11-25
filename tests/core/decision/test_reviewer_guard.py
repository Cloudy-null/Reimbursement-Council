"""The case reviewer can only send a claim to a person. These tests prove it over a grid of
claims (every lane the council can pick) and every reviewer score from 0 to 1."""

import itertools
from collections.abc import Sequence

import pytest

from reimbursement_council.core.decision.lanes import LaneChoice, choose_lane
from reimbursement_council.core.decision.reviewer_guard import DecideLane, apply_reviewer
from reimbursement_council.core.models.common import RuleName, RuleOutcome
from reimbursement_council.core.models.decision import PayoutResult, RuleResult, Vote
from tests.factories import repo_settings, settings_with

RULES: list[RuleName] = ["late", "policy_inactive", "person_not_covered", "excluded_service"]
PAYOUT = PayoutResult(
    requested=17250,
    network_cap_cut=0,
    copay=1500,
    limit_cut=0,
    vat_paid=2025,
    calculated=15525,
    unmatched_items=[],
    is_partial=False,
)
REQUEST = Vote(
    member="document_checker",
    score=0.5,
    reason="r",
    evidence=[],
    request="Please confirm the treatment_date.",
    request_kind="confirm_field",
    request_field="treatment_date",
)


def rules(outcome: RuleOutcome = "pass") -> list[RuleResult]:
    return [
        RuleResult(rule=rule, outcome=outcome if rule == "late" else "pass", reason="r", fields=[])
        for rule in RULES
    ]


def votes(*scores: float) -> list[Vote]:
    return [Vote(member="price_checker", score=s, reason="r", evidence=[]) for s in scores]


def reviewer(score: float, weight: float = 1.0) -> Vote:
    return Vote(member="case_reviewer", score=score, weight=weight, reason="r", evidence=[])


def decider(
    council: Sequence[Vote],
    rule_results: list[RuleResult],
    payout: PayoutResult | None = PAYOUT,
    retries_used: int = 0,
) -> DecideLane:
    def decide(p_good: float, disagreement: float) -> LaneChoice:
        return choose_lane(
            rule_results, council, p_good, disagreement, payout, retries_used, repo_settings()
        )

    return decide


COUNCILS = [votes(1.0, 1.0, 1.0), votes(0.95, 0.9, 1.0), votes(0.7, 0.8), votes(0.2, 0.3)]
SITUATIONS = [
    ("clean", rules(), PAYOUT, 0),
    ("hard rule failed", rules("fail"), PAYOUT, 0),
    ("unclear rule", rules("not_sure"), PAYOUT, 0),
    ("no payout", rules(), None, 0),
    ("no retries", rules("not_sure"), PAYOUT, 9),
]
REVIEWER_SCORES = [i / 20 for i in range(21)]


@pytest.mark.parametrize("situation", SITUATIONS, ids=[s[0] for s in SITUATIONS])
def test_reviewer_only_ever_moves_an_approve_to_a_person(
    situation: tuple[str, list[RuleResult], PayoutResult | None, int],
) -> None:
    _, rule_results, payout, retries = situation
    for council, score, weight in itertools.product(COUNCILS, REVIEWER_SCORES, [0.5, 1.0, 3.0]):
        extra = [REQUEST] if council[0].score < 0.5 else []
        members = [*council, *extra]
        decide = decider(members, rule_results, payout, retries)
        without = apply_reviewer(members, None, decide, repo_settings())
        with_it = apply_reviewer(members, reviewer(score, weight), decide, repo_settings())
        assert with_it.p_good <= without.p_good
        assert with_it.combined_score <= without.combined_score
        assert with_it.disagreement >= without.disagreement
        if without.choice.lane == "auto_approve":
            assert with_it.choice.lane in ("auto_approve", "human_review")
        else:
            assert with_it.choice == without.choice  # reject, self_fix, review: untouched
        assert with_it.changed_lane == (with_it.choice.lane != without.choice.lane)


def test_no_reviewer_is_the_plain_council() -> None:
    decide = decider(votes(1.0, 1.0), rules())
    result = apply_reviewer(votes(1.0, 1.0), None, decide, repo_settings())
    assert result.choice.lane == "auto_approve" and not result.changed_lane


def test_a_low_reviewer_score_sends_an_approve_to_a_person() -> None:
    decide = decider(votes(1.0, 1.0, 1.0), rules())
    result = apply_reviewer(votes(1.0, 1.0, 1.0), reviewer(0.1), decide, repo_settings())
    assert result.choice.lane == "human_review" and result.changed_lane
    assert "AI case reviewer" in result.choice.reason and "floor" in result.choice.reason


def test_a_strong_disagreement_sends_an_approve_to_a_person() -> None:
    settings = repo_settings()
    members = settings.decision.members
    low_floor = members.model_copy(
        update={"case_reviewer": members.case_reviewer.model_copy(update={"score_floor": 0.0})}
    )
    changed = settings_with(members=low_floor, disagreement_routing_enabled=False)
    decide = decider(votes(1.0, 1.0, 1.0), rules())
    result = apply_reviewer(votes(1.0, 1.0, 1.0), reviewer(0.5, weight=0.01), decide, changed)
    assert result.choice.lane == "human_review"
    assert "disagrees" in result.choice.reason


def test_an_agreeing_reviewer_keeps_the_approve() -> None:
    decide = decider(votes(1.0, 1.0, 1.0), rules())
    result = apply_reviewer(votes(1.0, 1.0, 1.0), reviewer(1.0), decide, repo_settings())
    assert result.choice.lane == "auto_approve" and not result.changed_lane


def test_a_rejected_claim_stays_rejected_whatever_the_reviewer_says() -> None:
    decide = decider(votes(1.0), rules("fail"))
    for score in (0.0, 1.0):
        result = apply_reviewer(votes(1.0), reviewer(score), decide, repo_settings())
        assert result.choice.lane == "auto_reject"


def test_the_grid_covers_every_lane_and_both_reviewer_effects() -> None:
    seen: set[tuple[str, str]] = set()
    for (_, rule_results, payout, retries), council, score in itertools.product(
        SITUATIONS, COUNCILS, REVIEWER_SCORES
    ):
        members = [*council, *([REQUEST] if council[0].score < 0.5 else [])]
        decide = decider(members, rule_results, payout, retries)
        without = apply_reviewer(members, None, decide, repo_settings()).choice.lane
        with_it = apply_reviewer(members, reviewer(score), decide, repo_settings()).choice.lane
        seen.add((without, with_it))
    assert {
        ("auto_approve", "auto_approve"),
        ("auto_approve", "human_review"),
        ("auto_reject", "auto_reject"),
        ("self_fix", "self_fix"),
        ("human_review", "human_review"),
    } <= seen
