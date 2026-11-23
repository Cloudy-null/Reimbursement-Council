from reimbursement_council.core.decision.blockers import approval_blockers
from reimbursement_council.core.models.claim import CheckResult, ExtractionResult
from reimbursement_council.core.models.decision import PayoutResult
from tests.factories import make_claim, make_extraction, make_field, repo_settings

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
FAILED = CheckResult(name="items_sum_to_subtotal", passed=False, details="d", fields=["subtotal"])


def receipt(
    total_confidence: float = 1.0, checks: list[CheckResult] | None = None
) -> ExtractionResult:
    return make_extraction([make_field("total", "17250", total_confidence)], checks=checks or [])


def test_clean_receipt_has_no_blockers() -> None:
    assert approval_blockers(make_claim(), receipt(), PAYOUT, repo_settings()) == []


def test_failed_check_blocks() -> None:
    blockers = approval_blockers(make_claim(), receipt(checks=[FAILED]), PAYOUT, repo_settings())
    assert len(blockers) == 1 and "items_sum_to_subtotal" in blockers[0]


def test_missing_or_unclear_total_blocks() -> None:
    assert approval_blockers(make_claim(), receipt(total_confidence=0.5), PAYOUT, repo_settings())
    no_total = make_extraction([])
    assert approval_blockers(make_claim(), no_total, PAYOUT, repo_settings())


def test_payout_above_receipt_total_blocks() -> None:  # final review: overpayment
    too_much = PAYOUT.model_copy(update={"calculated": 31050})
    blockers = approval_blockers(make_claim(), receipt(), too_much, repo_settings())
    assert any("above the receipt total" in b for b in blockers)


def test_second_receipt_blocks() -> None:  # final review: second receipt ignored
    claim = make_claim()
    second = claim.documents[0].model_copy(update={"document_id": "doc-2", "kind": "invoice"})
    two = claim.model_copy(update={"documents": [claim.documents[0], second]})
    blockers = approval_blockers(two, receipt(), PAYOUT, repo_settings())
    assert any("2 receipts" in b for b in blockers)


def test_no_extraction_adds_nothing_here() -> None:
    assert approval_blockers(make_claim(), None, None, repo_settings()) == []
