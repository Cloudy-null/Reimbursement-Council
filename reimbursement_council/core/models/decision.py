"""Rule results, votes, payout and the final decision."""

from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from reimbursement_council.core.models.case_review import CaseReview
from reimbursement_council.core.models.claim import CheckResult, FieldEdit
from reimbursement_council.core.models.common import (
    CrossCheckName,
    DocumentKind,
    FieldName,
    Halalas,
    Lane,
    MemberName,
    Model,
    Outcome,
    RequestKind,
    RuleName,
    RuleOutcome,
    Score,
)


class RuleResult(Model):
    rule: RuleName
    outcome: RuleOutcome
    reason: str
    fields: list[str]


class Vote(Model):
    member: MemberName
    score: Score
    weight: float = Field(default=1.0, ge=0.0)
    reason: str
    evidence: list[str]
    request: str | None = None
    request_kind: RequestKind | None = None
    request_field: str | None = None

    @model_validator(mode="after")
    def request_all_or_nothing(self) -> Self:
        parts = (self.request, self.request_kind, self.request_field)
        if any(part is not None for part in parts) and any(part is None for part in parts):
            raise ValueError("request, request_kind and request_field are all set or all empty")
        return self


class SelfFixRequest(Model):
    kind: RequestKind
    field: str
    text: str
    documents: list[str] = Field(default_factory=list)  # kinds that disagree, for fix_mismatch


class PayoutResult(Model):
    requested: Halalas
    network_cap_cut: Halalas
    copay: Halalas
    limit_cut: Halalas
    vat_paid: Halalas
    calculated: Halalas
    unmatched_items: list[str]
    is_partial: bool


class MemberMessage(Model):
    en: str
    ar: str


class DocumentNeed(Model):
    """One group of documents the claim needs: any one kind in the group is enough."""

    group: list[DocumentKind]
    satisfied: bool
    request: MemberMessage


class CrossCheckResult(Model):
    """Whether documents agree. passed is None when there is not enough data to compare."""

    name: CrossCheckName
    passed: bool | None
    field: FieldName
    document_ids: list[str]
    details: str


class Decision(Model):
    claim_id: str
    decided_at: AwareDatetime
    config_version: str
    combined_score: Score
    p_good: Score
    disagreement: Score
    payout_requested: Halalas | None
    payout_calculated: Halalas | None
    expected_loss: Halalas | None
    reviewer_time_value: Halalas
    lane: Lane
    lane_reason: str
    outcome: Outcome
    self_fix_request: SelfFixRequest | None
    member_message: MemberMessage
    votes: list[Vote]
    rule_results: list[RuleResult]
    check_results: list[CheckResult]
    edits: list[FieldEdit] = Field(default_factory=list)
    # What the pipeline found about the documents, so a run can be scored (Task 11).
    document_kinds: dict[str, DocumentKind] = Field(default_factory=dict)
    needs_missing: list[list[DocumentKind]] = Field(default_factory=list)
    cross_checks: list[CrossCheckResult] = Field(default_factory=list)
    # The AI case reviewer (decision 010). None when it is switched off in config.
    case_review: CaseReview | None = None
