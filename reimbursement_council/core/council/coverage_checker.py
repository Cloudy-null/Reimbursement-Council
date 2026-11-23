"""Coverage checker: how sure we are of the payout amount.

Score is the share of the billed amount we can price from the price list. Items we cannot
price get no request: the member cannot fix our price list, so a human looks instead.
"""

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.case import ClaimCase
from reimbursement_council.core.models.decision import Vote

MEMBER = "coverage_checker"


def vote(case: ClaimCase, settings: Settings) -> Vote:
    config = settings.decision.members.coverage_checker
    extraction = case.extraction
    if extraction is None:
        return Vote(member=MEMBER, score=0.0, reason="No receipt to price.", evidence=[])
    if case.payout is None:
        return Vote(
            member=MEMBER,
            score=config.no_items_score,
            reason="The receipt has no line items, so the payout cannot be priced.",
            evidence=[],
            request="Please add an itemized invoice that lists each service.",
            request_kind="add_document",
            request_field="itemized_invoice",
        )

    total = sum(item.amount for item in extraction.line_items)
    matched = sum(
        item.amount
        for item in extraction.line_items
        if (item.service_code or "") in settings.prices
    )
    share_without_amounts = 0.0 if case.payout.unmatched_items else 1.0
    share = matched / total if total > 0 else share_without_amounts
    reason = f"The price list covers {share:.2f} of the billed amount."
    return Vote(
        member=MEMBER, score=share, reason=reason, evidence=list(case.payout.unmatched_items)
    )
