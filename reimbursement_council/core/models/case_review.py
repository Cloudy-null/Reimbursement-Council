"""The AI case reviewer: what it reads (the case summary), what it said (the review), and
whether it may be used (its health). See docs/decisions/010-ai-case-reviewer.md."""

from typing import Literal

from pydantic import AwareDatetime, Field

from reimbursement_council.core.models.common import (
    DocumentKind,
    FieldName,
    FieldSource,
    MemberName,
    Model,
    RuleOutcome,
    Score,
)

ReviewStatus = Literal["used", "discarded", "skipped", "benched"]
"""used: the score was checked and taken into account. discarded: the answer broke the schema
or cited a value we did not read. skipped: no answer (timeout, error, lane not reviewed, model
not connected). benched: the reviewer is switched off by its health checks."""

ReviewProblem = Literal[
    "schema",
    "citation",
    "timeout",
    "error",
    "not_connected",
    "unchecked",
    "lane_not_reviewed",
    "benched",
]


class SummaryField(Model):
    """A value read from a document. Money is in SAR with two decimals, for example 172.50."""

    document_kind: DocumentKind
    name: FieldName
    value: str
    confidence: Score
    source: FieldSource


class SummaryItem(Model):
    description: str
    service_code: str | None
    quantity: int = Field(ge=1)
    amount_sar: str
    confidence: Score


class SummaryCheck(Model):
    """An arithmetic check on a document or a check across documents. passed None: not run."""

    name: str
    passed: bool | None
    details: str


class SummaryRule(Model):
    rule: str
    outcome: RuleOutcome
    reason: str


class SummaryVote(Model):
    member: MemberName
    score: Score
    reason: str


class ReviewSummary(Model):
    """Everything the case reviewer reads. Built in core from the claim case (pure)."""

    claim_id: str
    categories: list[str]
    fields: list[SummaryField]
    line_items: list[SummaryItem]
    checks: list[SummaryCheck]
    rules: list[SummaryRule]
    payout_requested_sar: str | None
    payout_calculated_sar: str | None
    member_votes: list[SummaryVote]


class CitedField(Model):
    name: str
    value: str


class CaseReview(Model):
    """What the case reviewer did on one claim, stored on the Decision and in the export."""

    status: ReviewStatus
    problem: ReviewProblem | None = None  # why it was discarded or skipped
    score: Score | None = None  # set only when status is used
    weight: float = Field(default=0.0, ge=0.0)
    reason: str | None = None  # the model's one-line reason (also kept when discarded)
    cited_fields: list[CitedField] = Field(default_factory=list)
    model: str
    prompt_version: str
    changed_lane: bool = False  # True when it sent a claim that would be approved to a person
    effect: str = ""  # plain words: what it changed, or why nothing


class GoldenCase(Model):
    """One case of the golden set: a summary and what a good reviewer must say about it."""

    name: str
    kind: Literal["clear_good", "clear_bad", "tricky", "injection"]
    expected: Literal["good", "bad"]
    note: str
    summary: ReviewSummary


class GoldenResult(Model):
    name: str
    expected: Literal["good", "bad"]
    status: ReviewStatus
    problem: ReviewProblem | None
    score: Score | None
    passed: bool


class RecentReview(Model):
    status: ReviewStatus
    score: Score | None


HealthStatus = Literal["unchecked", "healthy", "benched"]


class ReviewerHealth(Model):
    """Whether the reviewer may be used. A benched reviewer never re-enables itself."""

    status: HealthStatus = "unchecked"
    bench_reason: str | None = None
    benched_at: AwareDatetime | None = None
    last_check_at: AwareDatetime | None = None
    last_check_passed: bool | None = None
    golden_pass_rate: Score | None = None
    model: str | None = None  # model and prompt version of the last check
    prompt_version: str | None = None
    recent: list[RecentReview] = Field(default_factory=list)


class HealthReport(Model):
    """The health state for a screen (no HTML here): healthy, benched, unchecked or off."""

    state: Literal["off", "unchecked", "healthy", "benched"]
    last_check_at: AwareDatetime | None
    golden_pass_rate: Score | None
    bench_reason: str | None
    model: str
    prompt_version: str
    discarded_rate: Score | None
    score_spread: float | None
    recent_answers: int
