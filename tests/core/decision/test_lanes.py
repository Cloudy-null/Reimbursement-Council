from reimbursement_council.config.models import Settings
from reimbursement_council.core.decision.lanes import LaneChoice, choose_lane, expected_loss
from reimbursement_council.core.models.common import RuleName, RuleOutcome
from reimbursement_council.core.models.decision import PayoutResult, RuleResult, Vote
from tests.factories import repo_settings, settings_with

RULES: list[RuleName] = [
    "late",
    "policy_inactive",
    "person_not_covered",
    "excluded_service",
    "duplicate",
    "multiple_patients",
]
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
PARTIAL = PAYOUT.model_copy(update={"network_cap_cut": 25000, "is_partial": True})
UNMATCHED = PAYOUT.model_copy(update={"unmatched_items": ["Physio session"], "is_partial": True})
PLAIN_VOTES = [Vote(member="price_checker", score=1.0, reason="r", evidence=[])]
REQUEST_VOTES = [
    Vote(
        member="document_checker",
        score=0.6,
        reason="r",
        evidence=[],
        request="Please confirm the treatment_date.",
        request_kind="confirm_field",
        request_field="treatment_date",
    )
]


def rules(**outcomes: RuleOutcome) -> list[RuleResult]:
    return [
        RuleResult(
            rule=rule, outcome=outcomes.get(rule, "pass"), reason="r", fields=["treatment_date"]
        )
        for rule in RULES
    ]


def lane(
    p_good: float = 0.975,
    disagreement: float = 0.04,
    payout: PayoutResult | None = PAYOUT,
    votes: list[Vote] = PLAIN_VOTES,
    retries_used: int = 0,
    rule_results: list[RuleResult] | None = None,
    settings: Settings | None = None,
) -> LaneChoice:
    return choose_lane(
        rules() if rule_results is None else rule_results,
        votes,
        p_good,
        disagreement,
        payout,
        retries_used,
        settings or repo_settings(),
    )


def test_expected_loss() -> None:
    assert expected_loss(0.975, 15525) == 388
    assert expected_loss(1.0, 15525) == 0
    assert expected_loss(0.0, 15525) == 15525


def test_hard_fail_rejects_even_with_high_score() -> None:
    choice = lane(p_good=1.0, rule_results=rules(late="fail"))
    assert (choice.lane, choice.outcome) == ("auto_reject", "complete")
    assert "late" in choice.reason


def test_not_sure_goes_to_self_fix_with_vote_request() -> None:
    choice = lane(rule_results=rules(late="not_sure"), votes=REQUEST_VOTES)
    assert (choice.lane, choice.outcome) == ("self_fix", "queued")
    assert choice.request is not None
    assert (choice.request.kind, choice.request.field) == ("confirm_field", "treatment_date")


def test_not_sure_without_vote_request_confirms_rule_field() -> None:
    choice = lane(rule_results=rules(policy_inactive="not_sure"))
    assert choice.lane == "self_fix" and choice.request is not None
    assert (choice.request.kind, choice.request.field) == ("confirm_field", "treatment_date")


def test_retries_exhausted_goes_to_human() -> None:  # Review Focus 5
    choice = lane(
        0.4, 0.1, PAYOUT, REQUEST_VOTES, retries_used=2, rule_results=rules(late="not_sure")
    )
    assert choice.lane == "human_review" and choice.request is None


def test_low_score_request_exhausted_goes_to_human() -> None:  # Review Focus 5
    assert lane(p_good=0.4, votes=REQUEST_VOTES, retries_used=0).lane == "self_fix"
    assert lane(p_good=0.4, votes=REQUEST_VOTES, retries_used=2).lane == "human_review"


def test_approve_complete_and_partial() -> None:
    assert (lane().lane, lane().outcome) == ("auto_approve", "complete")
    partial = lane(payout=PARTIAL)
    assert (partial.lane, partial.outcome) == ("auto_approve", "partial")


def test_expected_loss_above_review_value_goes_to_human() -> None:
    choice = lane(p_good=0.8)  # 0.2 x 155.25 SAR = 31.05 SAR, above 25 SAR
    assert choice.lane == "human_review" and "expected loss" in choice.reason


def test_disagreement_blocks_approve_unless_switch_off() -> None:
    blocked = lane(disagreement=0.3)
    assert blocked.lane == "human_review" and "disagreement" in blocked.reason
    assert lane(
        disagreement=0.3, settings=settings_with(disagreement_routing_enabled=False)
    ).lane == ("auto_approve")


def test_no_payout_never_approves() -> None:
    assert lane(payout=None).lane == "human_review"


def test_unmatched_items_never_approve() -> None:  # Review Focus 4
    choice = lane(p_good=1.0, disagreement=0.0, payout=UNMATCHED)
    assert choice.lane == "human_review" and "Physio session" in choice.reason


def test_always_review_cap_switch() -> None:
    capped = settings_with(always_review_amount_enabled=True, always_review_amount_halalas=10000)
    assert lane(settings=capped).lane == "human_review"
    assert lane().lane == "auto_approve"


def test_fixed_threshold_when_cost_lanes_off() -> None:
    fixed = settings_with(cost_lanes_enabled=False)
    assert lane(p_good=0.95, settings=fixed).lane == "auto_approve"
    assert lane(p_good=0.85, settings=fixed).lane == "human_review"
    assert lane(p_good=0.85).lane == "auto_approve"  # 0.15 x 155.25 SAR = 23.29 SAR, below 25


def test_self_fix_switch_off_goes_to_human() -> None:
    off = settings_with(self_fix_enabled=False)
    assert lane(p_good=0.4, votes=REQUEST_VOTES, settings=off).lane == "human_review"
    assert lane(rule_results=rules(late="not_sure"), settings=off).lane == "human_review"


def test_no_reject_without_hard_rule() -> None:
    for payout in (PAYOUT, None, UNMATCHED):
        assert lane(p_good=0.0, disagreement=0.5, payout=payout).lane != "auto_reject"


def test_extra_blockers_stop_approval() -> None:  # final review
    choice = choose_lane(
        rules(), PLAIN_VOTES, 0.99, 0.0, PAYOUT, 0, repo_settings(), ["failed checks: x"]
    )
    assert choice.lane == "human_review" and "failed checks: x" in choice.reason
