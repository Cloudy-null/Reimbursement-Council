"""Shared types for every model: names, scores and money."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

Score = Annotated[float, Field(ge=0.0, le=1.0)]
"""A score or probability from 0 to 1. Never a percent."""

Halalas = Annotated[StrictInt, Field(ge=0)]
"""Money in halalas (1 SAR = 100 halalas). Never a float."""

Lane = Literal["auto_approve", "auto_reject", "self_fix", "human_review"]
Outcome = Literal["complete", "partial", "error", "queued"]
FieldSource = Literal["qr", "ocr", "vision", "member_confirmed", "member_typed", "reviewer"]
FieldName = Literal[
    "provider_name",
    "vat_number",
    "invoice_timestamp",
    "treatment_date",
    "subtotal",
    "vat_total",
    "total",
    "patient_name",
]
MONEY_FIELDS: frozenset[str] = frozenset({"subtotal", "vat_total", "total"})
DocumentKind = Literal["receipt", "invoice", "prescription", "medical_report", "other"]
PRIMARY_DOCUMENT_KINDS: tuple[DocumentKind, ...] = ("receipt", "invoice")
"""Documents that carry the amounts (billing documents)."""
BILLING_KINDS = PRIMARY_DOCUMENT_KINDS
RULE_FIELDS: frozenset[str] = MONEY_FIELDS | frozenset(
    {"treatment_date", "invoice_timestamp", "patient_name", "vat_number"}
)
"""Fields that change the payout or feed a hard rule. A member edit to one needs evidence."""
KindSource = Literal["detected", "member"]
EditEvidence = Literal["supports", "contradicts", "none"]
CrossCheckName = Literal["patient_matches_account", "dates_agree", "providers_agree"]
MemberName = Literal[
    "document_checker", "coverage_checker", "price_checker", "case_reviewer", "history_member"
]
RuleName = Literal[
    "late",
    "policy_inactive",
    "person_not_covered",
    "excluded_service",
    "duplicate",
    "multiple_patients",
    "member_edit",
]
RuleOutcome = Literal["pass", "fail", "not_sure"]
CheckName = Literal[
    "items_sum_to_subtotal", "vat_is_15_percent", "subtotal_plus_vat_is_total", "qr_matches_text"
]
RequestKind = Literal[
    "retake_photo", "add_document", "confirm_field", "check_photo", "fix_mismatch"
]


class Model(BaseModel):
    """Base for every domain model: unknown keys fail, objects never change."""

    model_config = ConfigDict(extra="forbid", frozen=True)
