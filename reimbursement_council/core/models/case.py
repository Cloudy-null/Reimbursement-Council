"""The claim case: everything a council member reads."""

from reimbursement_council.core.models.claim import Claim, ExtractionResult
from reimbursement_council.core.models.common import Model
from reimbursement_council.core.models.decision import PayoutResult, RuleResult
from reimbursement_council.core.models.reference import Member, MemberHistory, Policy, Provider


class ClaimCase(Model):
    claim: Claim
    member: Member
    policy: Policy
    provider: Provider
    history: MemberHistory
    extraction: ExtractionResult | None
    rule_results: list[RuleResult]
    payout: PayoutResult | None
