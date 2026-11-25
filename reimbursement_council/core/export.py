"""Build the claim export from a decided claim. Pure: no I/O, the caller hands everything in.

The export holds what a claims system needs to process the claim without opening the photos:
the values we read and how sure we are, the checks, the member's edits with their evidence,
the payout and the decision. See docs/INTEGRATION.md.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import PurePath

from reimbursement_council.core.models.claim import (
    Claim,
    Document,
    ExtractionResult,
    FieldEdit,
)
from reimbursement_council.core.models.common import DocumentKind, FieldName
from reimbursement_council.core.models.decision import (
    CrossCheckResult,
    Decision,
    PayoutResult,
)
from reimbursement_council.core.models.export import (
    ClaimExport,
    ExportDecision,
    ExportDocument,
    ExportField,
    ExportInvoice,
    ExportLineItem,
    ExportPayout,
    ExportProvider,
    ExportReview,
)
from reimbursement_council.core.models.reference import PriceListItem, Provider

APPROVING_REVIEWS = frozenset({"approve", "approve_amount"})


def _value(extraction: ExtractionResult | None, name: FieldName) -> str | None:
    best = None if extraction is None else extraction.best(name)
    return None if best is None else best.value


def _money(extraction: ExtractionResult | None, name: FieldName) -> int | None:
    return None if extraction is None else extraction.money(name)


def _category(code: str | None, prices: Mapping[str, PriceListItem]) -> str | None:
    return prices[code].category if code is not None and code in prices else None


def _invoice(
    extraction: ExtractionResult | None, prices: Mapping[str, PriceListItem]
) -> ExportInvoice | None:
    if extraction is None:
        return None
    items = [
        ExportLineItem(
            description=item.description,
            service_code=item.service_code,
            category=_category(item.service_code, prices),
            quantity=item.quantity,
            unit_price_halalas=item.unit_price,
            amount_halalas=item.amount,
            confidence=item.confidence,
        )
        for item in extraction.line_items
    ]
    return ExportInvoice(
        treatment_date=_value(extraction, "treatment_date"),
        invoice_timestamp=_value(extraction, "invoice_timestamp"),
        subtotal_halalas=_money(extraction, "subtotal"),
        vat_total_halalas=_money(extraction, "vat_total"),
        total_halalas=_money(extraction, "total"),
        line_items=items,
        checks=list(extraction.checks),
    )


def _provider(extraction: ExtractionResult | None, provider: Provider | None) -> ExportProvider:
    known = provider is not None and provider.provider_id != Provider.unknown(None).provider_id
    return ExportProvider(
        name=_value(extraction, "provider_name"),
        vat_number=_value(extraction, "vat_number"),
        provider_id=provider.provider_id if known and provider else None,
        in_network=provider.in_network if known and provider else None,
    )


def _document(
    document: Document, extraction: ExtractionResult | None, primary_id: str | None
) -> ExportDocument:
    fields = [] if extraction is None else extraction.fields
    return ExportDocument(
        document_id=document.document_id,
        kind=document.kind,
        kind_source=document.kind_source,
        file_name=PurePath(document.file_path.replace("\\", "/")).name,
        sha256=document.image_hash,
        is_primary=document.document_id == primary_id,
        fields=[
            ExportField(name=f.name, value=f.value, source=f.source, confidence=f.confidence)
            for f in fields
        ],
    )


def _payout(payout: PayoutResult | None) -> ExportPayout | None:
    if payout is None:
        return None
    return ExportPayout(
        requested_halalas=payout.requested,
        network_cap_cut_halalas=payout.network_cap_cut,
        copay_halalas=payout.copay,
        limit_cut_halalas=payout.limit_cut,
        vat_paid_halalas=payout.vat_paid,
        calculated_halalas=payout.calculated,
        unmatched_items=list(payout.unmatched_items),
        is_partial=payout.is_partial,
    )


def build_claim_export(
    claim: Claim,
    decision: Decision,
    documents: Sequence[Document],
    readings: Mapping[str, ExtractionResult],
    primary_id: str | None,
    categories: Sequence[str],
    missing: Sequence[Sequence[DocumentKind]],
    cross_checks: Sequence[CrossCheckResult],
    edits: Sequence[FieldEdit],
    provider: Provider | None,
    payout: PayoutResult | None,
    review: ExportReview | None,
    prices: Mapping[str, PriceListItem],
    now: datetime,
) -> ClaimExport:
    primary = None if primary_id is None else readings.get(primary_id)
    approved_by_person = review is not None and review.action in APPROVING_REVIEWS
    decided = decision.payout_calculated
    paid_as_decided = payout is not None and decided is not None and payout.calculated == decided
    return ClaimExport(
        exported_at=now,
        claim_id=claim.claim_id,
        status=claim.status,
        submitted_at=claim.submitted_at,
        member_id=claim.member_id,
        patient_member_id=claim.patient_member_id,
        policy_id=claim.policy_id,
        categories=list(categories),
        consented_at=claim.consented_at,
        ready_for_processing=approved_by_person
        if review is not None
        else decision.lane == "auto_approve" and paid_as_decided,
        provider=_provider(primary, provider),
        invoice=_invoice(primary, prices),
        documents=[_document(d, readings.get(d.document_id), primary_id) for d in documents],
        missing_documents=[list(group) for group in missing],
        cross_checks=list(cross_checks),
        member_edits=list(edits),
        payout=_payout(payout),
        decision=ExportDecision(
            lane=decision.lane,
            outcome=decision.outcome,
            reason=decision.lane_reason,
            p_good=decision.p_good,
            payout_calculated_halalas=decided,
            decided_at=decision.decided_at,
            config_version=decision.config_version,
            self_fix_request=decision.self_fix_request,
            member_message=decision.member_message,
            rule_results=list(decision.rule_results),
        ),
        review=review,
    )
