"""Lane groups (spec 6.4 and section 9): reject, then what the member can fix, then a human."""

from collections.abc import Sequence

from reimbursement_council.core.decision.document_requests import (
    DUPLICATE_REASON,
    human_reasons,
    member_requests,
)
from reimbursement_council.core.decision.lanes import LaneChoice, choose_lane
from reimbursement_council.core.models.claim import FieldEdit
from reimbursement_council.core.models.decision import RuleResult, SelfFixRequest
from tests.core.decision.test_document_requests import edit, mismatch, need
from tests.core.decision.test_lanes import PAYOUT, PLAIN_VOTES, RULES
from tests.factories import repo_settings

CONTRADICTING = RuleResult(
    rule="member_edit",
    outcome="not_sure",
    reason="The member typed 200.00, it shows 172.50.",
    fields=["total"],
)


def rules(*extra: RuleResult, **outcomes: str) -> list[RuleResult]:
    base = [
        RuleResult(rule=rule, outcome=outcomes.get(rule, "pass"), reason="r", fields=["x"])  # type: ignore[arg-type]
        for rule in RULES
    ]
    return base + list(extra)


def decide(
    rule_results: list[RuleResult],
    fixable: Sequence[SelfFixRequest] = (),
    edits: Sequence[FieldEdit] = (),
    retake_fields: Sequence[str] = (),
    retries_used: int = 0,
    p_good: float = 0.99,
) -> LaneChoice:
    return choose_lane(
        rule_results,
        PLAIN_VOTES,
        p_good,
        0.0,
        PAYOUT,
        retries_used,
        repo_settings(),
        [],
        member_fixable=fixable,
        human_only=human_reasons(rule_results, edits, retake_fields),
    )


def missing() -> list[SelfFixRequest]:
    return member_requests([need("prescription")], [], [], [], repo_settings())


def test_hard_rule_fail_beats_everything() -> None:
    choice = decide(rules(CONTRADICTING, late="fail"), fixable=missing())
    assert choice.lane == "auto_reject"


def test_missing_document_is_self_fix_even_with_a_high_score() -> None:
    choice = decide(rules(), fixable=missing(), p_good=1.0)
    assert choice.lane == "self_fix" and choice.request is not None
    assert (choice.request.kind, choice.request.field) == ("add_document", "prescription")


def test_missing_document_and_contradicting_edit_asks_the_member_first() -> None:
    choice = decide(rules(CONTRADICTING), fixable=missing())
    assert choice.lane == "self_fix"
    assert "prescription" in choice.reason and "200.00" in choice.reason


def test_second_try_with_only_the_contradicting_edit_left_goes_to_a_human() -> None:
    choice = decide(rules(CONTRADICTING), retries_used=1)
    assert choice.lane == "human_review" and "200.00" in choice.reason


def test_possible_duplicate_alone_goes_to_a_human() -> None:
    choice = decide(rules(duplicate="not_sure"))
    assert choice.lane == "human_review" and DUPLICATE_REASON in choice.reason


def test_no_evidence_total_edit_asks_for_a_retake_first() -> None:
    edits = [edit("total", "none")]
    fixable = member_requests([], [], edits, [], repo_settings())
    choice = decide(rules(), fixable=fixable, edits=edits)
    assert choice.lane == "self_fix" and choice.request is not None
    assert (choice.request.kind, choice.request.field) == ("retake_photo", "total")


def test_no_evidence_total_edit_after_the_retake_goes_to_a_human() -> None:
    edits = [edit("total", "none")]
    fixable = member_requests([], [], edits, ["total"], repo_settings())
    choice = decide(rules(), fixable=fixable, edits=edits, retake_fields=["total"], retries_used=1)
    assert fixable == [] and choice.lane == "human_review" and "total" in choice.reason


def test_member_fixable_with_no_retries_left_goes_to_a_human() -> None:
    choice = decide(rules(), fixable=missing(), retries_used=2)
    assert choice.lane == "human_review" and "prescription" in choice.reason


def test_missing_document_is_asked_before_a_mismatch() -> None:
    fixable = member_requests([need("prescription")], [mismatch()], [], [], repo_settings())
    choice = decide(rules(), fixable=fixable)
    assert choice.request is not None and choice.request.kind == "add_document"


def test_unclear_hard_rule_with_a_contradicting_edit_asks_the_member_first() -> None:
    choice = decide(rules(CONTRADICTING, late="not_sure"))
    assert choice.lane == "self_fix"


def test_duplicate_without_human_only_still_goes_to_a_human() -> None:
    choice = choose_lane(
        rules(duplicate="not_sure"), PLAIN_VOTES, 0.99, 0.0, PAYOUT, 0, repo_settings()
    )
    assert choice.lane == "human_review"
