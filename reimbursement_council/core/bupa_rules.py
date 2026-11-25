"""Document rules from Bupa's real decision (source: Bupa Arabia claim confirmation FAQ). Pure.

Each rule that is not met becomes a request to the member, so the claim is fixed before it is
sent on, never approved without it:
- optical: an eye test is needed; an eye prescription printed on the invoice counts
  (eye_prescription_on: one document can fill two roles).
- dental: the tooth number must be on the invoice or another document.
- a credit (pay later) invoice needs a proof of payment. CHECK in HANDOVER: whether a Tabby
  receipt counts; the real claim paid with Tabby was not held for it.
- invoice validity: the billing document has an invoice number, a VAT number and itemized lines.
- a document in a language other than Arabic or English needs a translation.
"""

import re
from collections.abc import Sequence

from reimbursement_council.config.models import BupaRulesConfig
from reimbursement_council.core.language import is_unsupported_language
from reimbursement_council.core.models.common import DocumentKind, Model
from reimbursement_council.core.models.decision import SelfFixRequest
from reimbursement_council.core.text import digits_to_ascii

BILLING: frozenset[str] = frozenset({"invoice", "receipt"})


class RuleDocument(Model):
    """What the rules need to know about one document."""

    document_id: str
    kind: DocumentKind
    text_lines: list[str]
    has_vat_number: bool = False
    has_line_items: bool = False


def _text(document: RuleDocument) -> str:
    return digits_to_ascii(" ".join(document.text_lines))


def _has_any(text: str, words: Sequence[str]) -> bool:
    lowered = text.casefold()
    return any(word.casefold() in lowered for word in words)


def eye_prescription_on(document: RuleDocument, config: BupaRulesConfig) -> bool:
    """An eye test printed on this document: every marker word is there (for example SPH and
    CYL), so a billing document also fills the prescription role for an optical claim."""
    text = _text(document).casefold()
    return all(word.casefold() in text for word in config.eye_test_markers)


def has_tooth_number(document: RuleDocument, config: BupaRulesConfig) -> bool:
    return re.search(config.tooth_number_pattern, _text(document), re.IGNORECASE) is not None


def has_invoice_number(document: RuleDocument, config: BupaRulesConfig) -> bool:
    return re.search(config.invoice_number_pattern, _text(document), re.IGNORECASE) is not None


def _readable(document: RuleDocument) -> bool:
    return any(line.strip() for line in document.text_lines)


def _request(field: str) -> SelfFixRequest:
    return SelfFixRequest(kind="add_document", field=field, text=f"Please add the {field}.")


def rule_requests(
    documents: Sequence[RuleDocument],
    categories: Sequence[str],
    primary_id: str | None,
    config: BupaRulesConfig,
) -> list[SelfFixRequest]:
    """Requests for every rule the claim does not meet yet, in a fixed order."""
    if not config.enabled:
        return []
    requests: list[SelfFixRequest] = []
    billing = [d for d in documents if d.kind in BILLING]
    primary = next((d for d in documents if d.document_id == primary_id), None)
    if config.translation and any(
        is_unsupported_language(d.text_lines, config.unsupported_language) for d in documents
    ):
        requests.append(_request("translation"))
    # A document with no text (a QR-only or hand-made reading) cannot be judged on its text.
    if config.invoice_validity and primary is not None and _readable(primary):
        valid = (
            has_invoice_number(primary, config)
            and primary.has_vat_number
            and primary.has_line_items
        )
        if not valid:
            requests.append(_request("full_tax_invoice"))
    teeth_named = any(has_tooth_number(d, config) for d in documents)
    any_text = any(_readable(d) for d in documents)
    if config.tooth_number and "dental" in categories and any_text and not teeth_named:
        requests.append(_request("tooth_number"))
    if config.proof_of_payment and any(_has_any(_text(d), config.credit_words) for d in billing):
        proof = [d for d in documents if d.kind == "receipt" and d is not primary]
        if not proof:
            requests.append(_request("proof_of_payment"))
    return requests
