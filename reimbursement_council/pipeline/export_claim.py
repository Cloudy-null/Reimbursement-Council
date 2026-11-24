"""Rebuild a decided claim's export from what is stored: the claim, its decision, the stored
readings and any review. The photos are not read again."""

from datetime import datetime

from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.config.models import Settings
from reimbursement_council.core.export import build_claim_export
from reimbursement_council.core.models.claim import Claim, Document, ReaderOutput
from reimbursement_council.core.models.export import ClaimExport, ExportReview
from reimbursement_council.core.models.reference import ReferenceData
from reimbursement_council.core.payout import calculate_payout
from reimbursement_council.pipeline.document_set import read_document_set
from reimbursement_council.pipeline.process_claim import patient_of


class _StoredReadingsOnly:
    """A reader that refuses: a document with no stored reading is exported as unread."""

    def read(self, document: Document) -> ReaderOutput:
        raise ValueError(f"no stored reading for document {document.document_id}")


def export_claim(
    claim: Claim, store: ClaimStore, reference: ReferenceData, settings: Settings, now: datetime
) -> ClaimExport | None:
    """The claim's export, or None when it has no decision yet (a draft)."""
    decision = store.load_decision(claim.claim_id)
    if decision is None:
        return None
    member = reference.member(claim.member_id)
    documents = read_document_set(
        claim,
        patient_of(reference, claim, member),
        settings,
        lambda document: _StoredReadingsOnly(),
        store.load_readings(claim.claim_id),
    )
    primary = None if documents.primary_id is None else documents.readings[documents.primary_id]
    payout = None
    if primary is not None:
        payout = calculate_payout(
            primary,
            reference.policy(claim.policy_id),
            reference.history(claim.patient_member_id),
            settings,
        )
    vat = None if primary is None else primary.best("vat_number")
    stored_review = store.load_review(claim.claim_id)
    review = (
        None
        if stored_review is None
        else ExportReview(
            action=stored_review.action,
            amount_halalas=stored_review.amount,
            reason=stored_review.reason,
            finished_at=stored_review.finished_at,
        )
    )
    return build_claim_export(
        claim,
        decision,
        documents.documents,
        documents.readings,
        documents.primary_id,
        documents.categories,
        [need.group for need in documents.missing],
        documents.cross_checks,
        documents.edits,
        reference.provider_by_vat(None if vat is None else vat.value),
        payout,
        review,
        settings.prices,
        now,
    )
