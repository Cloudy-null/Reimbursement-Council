"""The claim case: everything a council member reads."""

from pydantic import Field

from reimbursement_council.core.models.claim import Claim, ExtractionResult
from reimbursement_council.core.models.common import Model
from reimbursement_council.core.models.decision import (
    CrossCheckResult,
    DocumentNeed,
    PayoutResult,
    RuleResult,
)
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
    documents_read: dict[str, ExtractionResult] = Field(default_factory=dict)
    needs: list[DocumentNeed] = Field(default_factory=list)
    cross_checks: list[CrossCheckResult] = Field(default_factory=list)
