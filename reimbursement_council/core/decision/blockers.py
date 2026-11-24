"""Data problems that stop auto approve even when the score is high.

A high score is not enough when the receipt itself does not add up: then a human looks,
or the member fixes it. Each blocker is a short plain reason for the reviewer.
"""

from collections.abc import Sequence

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import Claim, ExtractionResult
from reimbursement_council.core.models.decision import DocumentNeed, PayoutResult
from reimbursement_council.core.money import format_sar


def approval_blockers(
    claim: Claim,
    extraction: ExtractionResult | None,
    payout: PayoutResult | None,
    settings: Settings,
    missing: Sequence[DocumentNeed] = (),
    billing_totals_differ: bool = False,
) -> list[str]:
    """missing: required documents not in the claim. billing_totals_differ: two billing
    documents name different totals, so we do not know which purchase is claimed."""
    blockers: list[str] = []
    for need in missing:
        blockers.append(f"missing document: {' or '.join(need.group)}")
    if billing_totals_differ:
        blockers.append("the receipts or invoices in the claim show different totals")
    if extraction is None:
        return blockers

    failed = [check.name for check in extraction.checks if not check.passed]
    if failed:
        blockers.append(f"failed checks: {', '.join(failed)}")
    total_field = extraction.best("total")
    total = extraction.money("total")
    if total_field is None or total is None:
        blockers.append("the receipt total is missing")
    elif total_field.confidence < settings.decision.hard_rule_confidence_floor:
        blockers.append("the receipt total is unclear")
    elif payout is not None and payout.calculated > total:
        blockers.append(
            f"payout {format_sar(payout.calculated)} SAR is above the receipt total "
            f"{format_sar(total)} SAR"
        )
    return blockers
