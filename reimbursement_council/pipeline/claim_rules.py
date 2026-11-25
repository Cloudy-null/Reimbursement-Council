"""Glue between the document set and the Bupa FAQ document rules (core/bupa_rules.py)."""

from collections.abc import Mapping, Sequence

from reimbursement_council.config.models import Settings
from reimbursement_council.core.bupa_rules import (
    BILLING,
    RuleDocument,
    eye_prescription_on,
    rule_requests,
)
from reimbursement_council.core.models.claim import Document, ExtractionResult, ReaderOutput
from reimbursement_council.core.models.common import DocumentKind
from reimbursement_council.core.models.decision import SelfFixRequest


def rule_documents(
    documents: Sequence[Document],
    raw: Mapping[str, ReaderOutput],
    final: Mapping[str, ExtractionResult],
) -> list[RuleDocument]:
    return [
        RuleDocument(
            document_id=d.document_id,
            kind=d.kind,
            text_lines=list(raw[d.document_id].text_lines),
            has_vat_number=final[d.document_id].best("vat_number") is not None,
            has_line_items=bool(final[d.document_id].line_items),
        )
        for d in documents
        if d.document_id in raw and d.document_id in final
    ]


def kinds_with_eye_test(
    kinds: Sequence[DocumentKind], rule_docs: Sequence[RuleDocument], settings: Settings
) -> list[DocumentKind]:
    """One document can fill two roles: an invoice with an eye prescription printed on it also
    counts as the prescription an optical claim needs (source: Bupa Arabia claim FAQ)."""
    config = settings.documents.bupa_rules
    printed = (
        config.enabled
        and config.eye_test_on_invoice
        and any(d.kind in BILLING and eye_prescription_on(d, config) for d in rule_docs)
    )
    return [*kinds, "prescription"] if printed and "prescription" not in kinds else list(kinds)


def claim_rule_requests(
    rule_docs: Sequence[RuleDocument],
    categories: Sequence[str],
    primary_id: str | None,
    settings: Settings,
) -> list[SelfFixRequest]:
    return rule_requests(rule_docs, categories, primary_id, settings.documents.bupa_rules)
