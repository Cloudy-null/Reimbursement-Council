"""Read every document of a claim once and put together what the later stages need.

Steps: drop a second copy of the same file, read each document (or use the reading stored
when the member saw the check screen), find each document's type, judge the member's edits
against the evidence, pick the primary billing document, work out the categories, the
documents still needed and the cross-document checks, and flag member changes that a human
must see (a contradicting edit, or a type or category change that removes a required
document).
"""

import logging
from collections.abc import Callable, Mapping

from pydantic import Field

from reimbursement_council.adapters.readers import DocumentReader
from reimbursement_council.config.models import Settings
from reimbursement_council.core.claim_categories import claim_categories
from reimbursement_council.core.cross_checks import cross_checks
from reimbursement_council.core.decision.document_requests import shown_value
from reimbursement_council.core.document_kinds import detect_kind
from reimbursement_council.core.document_needs import document_needs
from reimbursement_council.core.edit_evidence import apply_edits, judge_edit
from reimbursement_council.core.extraction import extract_document
from reimbursement_council.core.models.claim import (
    Claim,
    Document,
    ExtractionResult,
    FieldEdit,
    ReaderOutput,
)
from reimbursement_council.core.models.common import (
    BILLING_KINDS,
    MONEY_FIELDS,
    DocumentKind,
    Model,
)
from reimbursement_council.core.models.decision import (
    CrossCheckResult,
    DocumentNeed,
    RuleResult,
    SelfFixRequest,
)
from reimbursement_council.core.models.reference import Member
from reimbursement_council.pipeline.claim_rules import (
    claim_rule_requests,
    kinds_with_eye_test,
    rule_documents,
)

logger = logging.getLogger(__name__)


class DocumentSet(Model):
    documents: list[Document]
    readings: dict[str, ExtractionResult]
    primary_id: str | None
    categories: list[str]
    detected_categories: list[str]
    needs: list[DocumentNeed]
    cross_checks: list[CrossCheckResult]
    edits: list[FieldEdit]
    edit_rule_results: list[RuleResult]
    billing_documents_differ: bool
    notes: list[str]
    # What each reader returned, before anything was changed: stored so an export or a later
    # check can be rebuilt without reading the photos again.
    raw_readings: dict[str, ReaderOutput] = Field(default_factory=dict)
    # Bupa FAQ document rules not met yet (core/bupa_rules.py): requests to the member.
    rule_requests: list[SelfFixRequest] = Field(default_factory=list)

    @property
    def missing(self) -> list[DocumentNeed]:
        return [need for need in self.needs if not need.satisfied]


def _without_copies(claim: Claim) -> tuple[list[Document], list[str]]:
    kept: list[Document] = []
    notes: list[str] = []
    seen: set[str] = set()
    for document in claim.documents:
        if document.image_hash is not None and document.image_hash in seen:
            notes.append(f"document {document.document_id} is the same file as another one")
            continue
        if document.image_hash is not None:
            seen.add(document.image_hash)
        kept.append(document)
    return kept, notes


def _read(
    document: Document,
    stored: Mapping[str, ReaderOutput],
    reader_for: Callable[[Document], DocumentReader],
) -> tuple[ReaderOutput, str | None]:
    """The stored reading, or a fresh one. A document that cannot be read (unknown file type,
    missing file) gives an empty reading and a note, so one bad file never stops the claim."""
    if document.document_id in stored:
        return stored[document.document_id], None
    try:
        return reader_for(document).read(document), None
    except (ValueError, OSError) as error:
        logger.warning("document %s could not be read: %s", document.document_id, error)
        note = f"document {document.document_id} could not be read: {error}"
        return ReaderOutput(fields=[], line_items=[], qr_payloads=[]), note


def _with_kind(document: Document, reading: ReaderOutput, settings: Settings) -> Document:
    """Detect the kind unless the member set it; the detected kind is always kept, so a member
    change can be compared with it. A reading with no text and no QR is "other": nothing on it
    says what it is."""
    # The local model's kind_hint is stored for people only: a required document is never
    # satisfied by what the model says the page is (code review, core day 4).
    detected = detect_kind(reading.text_lines, reading.qr_payloads, settings.documents)
    if document.kind_source == "member":
        return document.model_copy(update={"detected_kind": detected})
    return document.model_copy(update={"kind": detected, "detected_kind": detected})


def _without_money(reading: ReaderOutput) -> ReaderOutput:
    """Money and line items count only on billing documents (spec 6.3), so a note or a report
    with a number on it can never back a member's edit to the total."""
    fields = [f for f in reading.fields if f.name not in MONEY_FIELDS]
    return reading.model_copy(update={"fields": fields, "line_items": []})


def _primary(documents: list[Document], raw: Mapping[str, ReaderOutput]) -> str | None:
    bills = [d for d in documents if d.kind in BILLING_KINDS]
    with_qr = [d for d in bills if raw[d.document_id].qr_payloads]
    invoices = [d for d in bills if d.kind == "invoice"]
    chosen = with_qr or invoices or bills
    return chosen[0].document_id if chosen else None


def _judged_edits(
    claim: Claim, readings: Mapping[str, ExtractionResult], settings: Settings
) -> tuple[list[FieldEdit], list[str]]:
    judged: list[FieldEdit] = []
    notes: list[str] = []
    for edit in claim.edits:
        own = readings.get(edit.document_id)
        if own is None:
            notes.append(f"an edit names document {edit.document_id}, which is not in the claim")
            continue
        read = own.best(edit.field)
        edit = edit.model_copy(update={"read_value": None if read is None else read.value})
        others = [r for doc_id, r in readings.items() if doc_id != edit.document_id]
        judged.append(judge_edit(edit, own, others, settings))
    return judged, notes


def _unsatisfied(needs: list[DocumentNeed]) -> set[tuple[DocumentKind, ...]]:
    return {tuple(need.group) for need in needs if not need.satisfied}


def _edit_rules(
    edits: list[FieldEdit],
    detected_needs: list[DocumentNeed],
    needs: list[DocumentNeed],
) -> list[RuleResult]:
    rules = [
        RuleResult(
            rule="member_edit",
            outcome="not_sure",
            reason=(
                f"The member typed {shown_value(edit.field, edit.typed_value)} "
                f"for the {edit.field}, the document shows "
                f"{shown_value(edit.field, edit.read_value or 'nothing')}: it {edit.evidence_note}."
            ),
            fields=[edit.field],
        )
        for edit in edits
        if edit.evidence == "contradicts"
    ]
    removed = _unsatisfied(detected_needs) - _unsatisfied(needs)
    if removed:
        names = ", ".join(" or ".join(group) for group in sorted(removed))
        rules.append(
            RuleResult(
                rule="member_edit",
                outcome="not_sure",
                reason=f"The member changed a type or the category, so {names} is no longer asked.",
                fields=["documents"],
            )
        )
    return rules


def _billing_documents_differ(
    documents: list[Document], readings: Mapping[str, ExtractionResult]
) -> bool:
    """Two billing documents with different totals or VAT numbers are two purchases, so we do
    not know which one is claimed."""
    bills = [readings[d.document_id] for d in documents if d.kind in BILLING_KINDS]
    totals = {total for r in bills if (total := r.money("total")) is not None}
    vat_numbers = {field.value for r in bills if (field := r.best("vat_number")) is not None}
    return len(totals) > 1 or len(vat_numbers) > 1


def read_document_set(
    claim: Claim,
    patient: Member,
    settings: Settings,
    reader_for: Callable[[Document], DocumentReader],
    readings: Mapping[str, ReaderOutput] | None = None,
) -> DocumentSet:
    stored = readings or {}
    documents, notes = _without_copies(claim)
    raw: dict[str, ReaderOutput] = {}
    for document in documents:
        reading, note = _read(document, stored, reader_for)
        raw[document.document_id] = reading
        notes += [note] if note else []
    as_read = dict(raw)
    documents = [_with_kind(d, raw[d.document_id], settings) for d in documents]
    raw = {
        d.document_id: (
            raw[d.document_id] if d.kind in BILLING_KINDS else _without_money(raw[d.document_id])
        )
        for d in documents
    }
    first_reading = {
        doc_id: extract_document(doc_id, reading, settings) for doc_id, reading in raw.items()
    }
    edits, edit_notes = _judged_edits(claim, first_reading, settings)
    edited_ids = {edit.document_id for edit in edits}
    final = {
        doc_id: (
            extract_document(doc_id, apply_edits(doc_id, raw[doc_id], edits, settings), settings)
            if doc_id in edited_ids
            else first_reading[doc_id]
        )
        for doc_id in raw
    }
    primary_id = _primary(documents, raw)
    items = [] if primary_id is None else final[primary_id].line_items
    detected_categories = claim_categories(items, settings.prices)
    categories = list(claim.claim_categories) or detected_categories
    rule_docs = rule_documents(documents, raw, final)
    kinds = kinds_with_eye_test([d.kind for d in documents], rule_docs, settings)
    detected_kinds = kinds_with_eye_test(
        [d.detected_kind or d.kind for d in documents], rule_docs, settings
    )
    needs = document_needs(categories, kinds, settings)
    detected_needs = document_needs(detected_categories, detected_kinds, settings)
    checks = (
        cross_checks([(d, final[d.document_id]) for d in documents], patient, categories, settings)
        if settings.decision.cross_checks_enabled
        else []
    )
    for note in notes + edit_notes:
        logger.info("claim %s: %s", claim.claim_id, note)
    return DocumentSet(
        documents=documents,
        readings=final,
        primary_id=primary_id,
        categories=categories,
        detected_categories=detected_categories,
        needs=needs,
        cross_checks=checks,
        edits=edits,
        edit_rule_results=_edit_rules(edits, detected_needs, needs),
        billing_documents_differ=_billing_documents_differ(documents, final),
        notes=notes + edit_notes,
        raw_readings=as_read,
        rule_requests=claim_rule_requests(rule_docs, categories, primary_id, settings),
    )
