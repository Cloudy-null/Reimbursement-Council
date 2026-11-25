"""One harness row per claim: the decision next to the generator's truth (run-set)."""

from typing import Any

from reimbursement_council.core.models.claim import Claim
from reimbursement_council.core.models.decision import Decision
from reimbursement_council.core.models.reference import ReferenceData
from reimbursement_council.synthetic.document_metrics import MISMATCH_DEFECTS
from reimbursement_council.synthetic.metrics import RunRow


def run_row(
    name: str,
    result: Decision,
    truth: dict[str, Any],
    first: Decision | None,
    past_claims: int | None,
) -> RunRow:
    # The truth's documents are those of the first try, so they are scored on it.
    read = first or result
    return RunRow(
        name=name,
        lane=result.lane,
        outcome=result.outcome,
        payout_calculated=result.payout_calculated,
        p_good=result.p_good,
        combined_score=result.combined_score,
        should_pay=truth["should_pay"],
        correct_payout=truth["correct_payout"],
        defects=truth["defects"],
        damage=truth["damage"],
        hard_rule_failed=any(r.outcome == "fail" for r in result.rule_results),
        kinds_read=dict(read.document_kinds),
        kinds_true=truth.get("document_kinds", {}),
        needs_flagged=[list(g) for g in read.needs_missing],
        needs_missing=truth.get("needs_missing", []),
        cross_check_failed=any(c.passed is False for c in read.cross_checks),
        cross_check_expected=bool(MISMATCH_DEFECTS & set(truth["defects"])),
        expected_lane=truth.get("expected_lane"),
        first_lane=None if first is None else first.lane,
        fix_tried=first is not None,
        past_claims=past_claims,
        reviewer_status=None if result.case_review is None else result.case_review.status,
    )


def past_claims_of(reference: ReferenceData, claim: Claim) -> int | None:
    try:
        return reference.history(claim.patient_member_id).past_claims
    except LookupError:
        return None
