"""Shared types for every model: names, scores and money."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

Score = Annotated[float, Field(ge=0.0, le=1.0)]
"""A score or probability from 0 to 1. Never a percent."""

Halalas = Annotated[StrictInt, Field(ge=0)]
"""Money in halalas (1 SAR = 100 halalas). Never a float."""

Lane = Literal["auto_approve", "auto_reject", "self_fix", "human_review"]
Outcome = Literal["complete", "partial", "error", "queued"]
FieldSource = Literal["qr", "ocr", "vision", "member_confirmed", "reviewer"]
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
]
RuleOutcome = Literal["pass", "fail", "not_sure"]
CheckName = Literal[
    "items_sum_to_subtotal", "vat_is_15_percent", "subtotal_plus_vat_is_total", "qr_matches_text"
]
RequestKind = Literal["retake_photo", "add_document", "confirm_field"]


class Model(BaseModel):
    """Base for every domain model: unknown keys fail, objects never change."""

    model_config = ConfigDict(extra="forbid", frozen=True)
