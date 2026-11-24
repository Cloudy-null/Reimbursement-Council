"""The claim export: structured, submission-ready claim data for a claims system (brief
deliverable 2). Its JSON Schema is generated from these models into
schemas/claim-export.schema.json, and docs/INTEGRATION.md explains every field.

Money is whole halalas (1 SAR = 100 halalas), so no amount is ever a float. Dates are
YYYY-MM-DD. Times carry a UTC offset. Ids point into the claims system's own member, policy and
provider records, so the export does not repeat names it does not need.
"""

from typing import Literal

from pydantic import AwareDatetime, Field

from reimbursement_council.core.models.claim import CheckResult, FieldEdit
from reimbursement_council.core.models.common import (
    DocumentKind,
    FieldName,
    FieldSource,
    Halalas,
    KindSource,
    Lane,
    Model,
    Outcome,
    Score,
)
from reimbursement_council.core.models.decision import (
    CrossCheckResult,
    MemberMessage,
    RuleResult,
    SelfFixRequest,
)

EXPORT_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class ExportField(Model):
    """One value read from a document, with where it came from and how sure we are."""

    name: FieldName
    value: str
    source: FieldSource
    confidence: Score


class ExportDocument(Model):
    document_id: str
    kind: DocumentKind
    kind_source: KindSource
    file_name: str
    sha256: str | None
    is_primary: bool  # the billing document the money comes from
    fields: list[ExportField]


class ExportLineItem(Model):
    description: str
    service_code: str | None
    category: str | None  # benefit category from the price list; None when not listed
    quantity: int = Field(ge=1)
    unit_price_halalas: Halalas
    amount_halalas: Halalas
    confidence: Score


class ExportProvider(Model):
    name: str | None
    vat_number: str | None
    provider_id: str | None  # None when the VAT number matches no known provider
    in_network: bool | None


class ExportInvoice(Model):
    """The billing document's values after the QR, the checks and any backed member edit."""

    treatment_date: str | None
    invoice_timestamp: str | None
    currency: Literal["SAR"] = "SAR"
    subtotal_halalas: Halalas | None
    vat_total_halalas: Halalas | None
    total_halalas: Halalas | None
    line_items: list[ExportLineItem]
    checks: list[CheckResult]


class ExportPayout(Model):
    requested_halalas: Halalas
    network_cap_cut_halalas: Halalas
    copay_halalas: Halalas
    limit_cut_halalas: Halalas
    vat_paid_halalas: Halalas
    calculated_halalas: Halalas
    unmatched_items: list[str]
    is_partial: bool


class ExportDecision(Model):
    lane: Lane
    outcome: Outcome
    reason: str
    p_good: Score
    decided_at: AwareDatetime
    config_version: str
    self_fix_request: SelfFixRequest | None
    member_message: MemberMessage
    rule_results: list[RuleResult]


class ExportReview(Model):
    action: Literal["approve", "approve_amount", "reject", "ask_member"]
    amount_halalas: Halalas | None
    reason: str
    finished_at: AwareDatetime


class ClaimExport(Model):
    schema_version: Literal["1.0"] = EXPORT_SCHEMA_VERSION
    exported_at: AwareDatetime
    claim_id: str
    status: str
    submitted_at: AwareDatetime
    member_id: str
    patient_member_id: str
    policy_id: str
    categories: list[str]
    consented_at: AwareDatetime | None
    ready_for_processing: bool  # auto approved, or a person has approved it
    provider: ExportProvider
    invoice: ExportInvoice | None  # None when no billing document could be read
    documents: list[ExportDocument]
    missing_documents: list[list[DocumentKind]]
    cross_checks: list[CrossCheckResult]
    member_edits: list[FieldEdit]
    payout: ExportPayout | None
    decision: ExportDecision
    review: ExportReview | None
