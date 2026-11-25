"""The check form: show read values as the member would type them, and turn what the member
sent back into FieldEdits, or into field errors that keep the rest of the input (Review Focus 4).

A field left empty or unchanged makes no edit, and an unchanged value is never refused (the
reader may have read a date that does not exist). The pipeline judges each edit against the
evidence; this module only checks that the typed text is a value at all. It also holds the
rules for the type and category the member picks.
"""

from collections.abc import Mapping, Sequence
from datetime import date

from reimbursement_council.core.models.claim import Document, FieldEdit
from reimbursement_council.core.models.common import MONEY_FIELDS, DocumentKind, FieldName
from reimbursement_council.core.money import format_sar, parse_sar_to_halalas

EDITABLE: tuple[FieldName, ...] = (
    "provider_name",
    "vat_number",
    "treatment_date",
    "patient_name",
    "subtotal",
    "vat_total",
    "total",
)
VAT_NUMBER_LENGTH = 15  # a Saudi VAT number is 15 digits (ZATCA)
DOCUMENT_KINDS: tuple[DocumentKind, ...] = (
    "invoice",
    "receipt",
    "prescription",
    "medical_report",
    "other",
)


def form_value(field: str, stored: str | None) -> str:
    """A stored value as the member sees it: money in SAR with two decimals."""
    if stored is None:
        return ""
    if field in MONEY_FIELDS and stored.isdigit():
        return format_sar(int(stored))
    return stored


def _normalized(field: str, text: str) -> tuple[str | None, str | None]:
    """(stored value, error key). Exactly one of the two is set."""
    if field in MONEY_FIELDS:
        halalas = parse_sar_to_halalas(text)
        return (None, "error_money") if halalas is None else (str(halalas), None)
    if field == "treatment_date":
        try:
            return date.fromisoformat(text).isoformat(), None
        except ValueError:
            return None, "error_date"
    if field == "vat_number":
        digits = "".join(text.split())
        ok = digits.isascii() and digits.isdigit() and len(digits) == VAT_NUMBER_LENGTH
        return (digits, None) if ok else (None, "error_vat")
    return " ".join(text.split()), None


def parse_edits(
    form: Mapping[str, str], primary_id: str, read_values: Mapping[FieldName, str | None]
) -> tuple[list[FieldEdit], dict[str, str]]:
    """(edits for fields whose value changed, error key per field that is not a value)."""
    edits: list[FieldEdit] = []
    errors: dict[str, str] = {}
    for field in EDITABLE:
        text = form.get(f"field_{field}", "").strip()
        read = read_values.get(field)
        if not text or text == form_value(field, read):
            continue
        value, error = _normalized(field, text)
        if error is not None:
            errors[field] = error
            continue
        if value is not None and value != read:
            edits.append(
                FieldEdit(document_id=primary_id, field=field, read_value=read, typed_value=value)
            )
    return edits, errors


def chosen_kinds(documents: Sequence[Document], form: Mapping[str, str]) -> list[Document]:
    """Each document with the type the member picked. Picking the detected type hands the
    document back to the reader; no pick leaves it as it is."""
    kinded = []
    for document in documents:
        chosen = form.get(f"kind_{document.document_id}", "")
        detected = document.detected_kind or document.kind
        if chosen == detected:
            document = document.model_copy(update={"kind": detected, "kind_source": "detected"})
        elif chosen in DOCUMENT_KINDS:
            document = document.model_copy(update={"kind": chosen, "kind_source": "member"})
        kinded.append(document)
    return kinded


def chosen_categories(category: str, valid: Sequence[str], detected: Sequence[str]) -> list[str]:
    """The member's category only when it is a real one and not what was found anyway; auto
    (empty) or the detected category clears an earlier choice."""
    return [category] if category in valid and category not in detected else []
