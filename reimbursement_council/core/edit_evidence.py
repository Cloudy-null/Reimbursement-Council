"""Is a value the member typed backed by the evidence? Pure logic, no I/O.

Evidence, in order: the QR on the same document, the same field on another document of the
claim, and (for money) the arithmetic checks run again with the typed value put in. One
agreeing source makes the edit "supports"; otherwise one disagreeing source makes it
"contradicts"; otherwise "none". What happens next (use it, ask for a retake, or a human)
is decided by the lanes, not here.
"""

from collections.abc import Sequence

from reimbursement_council.config.models import Settings
from reimbursement_council.core.extraction import arithmetic_checks
from reimbursement_council.core.models.claim import (
    ExtractedField,
    ExtractionResult,
    FieldEdit,
    ReaderOutput,
)
from reimbursement_council.core.models.common import MONEY_FIELDS, RULE_FIELDS
from reimbursement_council.core.text import normalize_text

NAME_FIELDS = frozenset({"patient_name", "provider_name"})


def _same(field: str, a: str, b: str) -> bool:
    if field in NAME_FIELDS:
        return sorted(normalize_text(a).split()) == sorted(normalize_text(b).split())
    return a.strip() == b.strip()


def _qr_verdict(edit: FieldEdit, own: ExtractionResult) -> bool | None:
    values = [f.value for f in own.fields if f.name == edit.field and f.source == "qr"]
    if not values:
        return None
    return any(_same(edit.field, edit.typed_value, value) for value in values)


def _other_documents_verdict(edit: FieldEdit, others: Sequence[ExtractionResult]) -> bool | None:
    values = [field.value for other in others if (field := other.best(edit.field)) is not None]
    if not values:
        return None
    return any(_same(edit.field, edit.typed_value, value) for value in values)


def _arithmetic_verdict(edit: FieldEdit, own: ExtractionResult, settings: Settings) -> bool | None:
    if edit.field not in MONEY_FIELDS or not edit.typed_value.isdigit():
        return None
    typed = ExtractedField(
        document_id=own.document_id,
        name=edit.field,
        value=edit.typed_value,
        original_text=edit.typed_value,
        source="member_typed",
        confidence=1.0,
    )
    fields = [f for f in own.fields if f.name != edit.field] + [typed]
    checks = arithmetic_checks(
        fields,
        own.line_items,
        settings.policy.vat_rate,
        settings.decision.arithmetic_tolerance_halalas,
    )
    relevant = [check for check in checks if edit.field in check.fields]
    if not relevant:
        return None
    return all(check.passed for check in relevant)


def judge_edit(
    edit: FieldEdit,
    own: ExtractionResult,
    others: Sequence[ExtractionResult],
    settings: Settings,
) -> FieldEdit:
    # (verdict, note when it agrees, note when it disagrees)
    verdicts = [
        (
            _qr_verdict(edit, own),
            "matches the QR code on this document",
            "does not match the QR code on this document",
        ),
        (
            _other_documents_verdict(edit, others),
            "matches another document in this claim",
            "does not match another document in this claim",
        ),
        (
            _arithmetic_verdict(edit, own, settings),
            "with it, the amounts on this document add up",
            "with it, the amounts on this document do not add up",
        ),
    ]
    for verdict, agrees, _ in verdicts:
        if verdict is True:
            return edit.model_copy(update={"evidence": "supports", "evidence_note": agrees})
    for verdict, _, disagrees in verdicts:
        if verdict is False:
            return edit.model_copy(update={"evidence": "contradicts", "evidence_note": disagrees})
    note = "nothing on the documents can confirm or deny it"
    return edit.model_copy(update={"evidence": "none", "evidence_note": note})


def _usable_confidence(edit: FieldEdit, settings: Settings) -> float | None:
    """The confidence to use a typed value with, or None when it must not be used."""
    if edit.evidence == "supports":
        return settings.decision.passed_check_confidence
    if edit.evidence == "none" and edit.field not in RULE_FIELDS:
        return settings.documents.unbacked_edit_confidence
    return None


def apply_edits(
    document_id: str, reading: ReaderOutput, edits: Sequence[FieldEdit], settings: Settings
) -> ReaderOutput:
    """The reading with each usable edit for this document put in as a member_typed field.
    A contradicting edit, or an unbacked edit on a money or hard rule field, is left out: the
    read value stays, and the reviewer sees both."""
    fields = list(reading.fields)
    for edit in edits:
        if edit.document_id != document_id:
            continue
        confidence = _usable_confidence(edit, settings)
        if confidence is None:
            continue
        fields = [f for f in fields if not (f.name == edit.field and f.source != "qr")]
        fields.append(
            ExtractedField(
                document_id=document_id,
                name=edit.field,
                value=edit.typed_value,
                original_text=edit.read_value or "",
                source="member_typed",
                confidence=confidence,
            )
        )
    return reading.model_copy(update={"fields": fields})
