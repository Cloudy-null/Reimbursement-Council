"""The check form: show read values as the member would type them, and turn what the member
sent back into FieldEdits, or into field errors that keep the rest of the input (Review Focus 4).

A field left empty or unchanged makes no edit. The pipeline judges each edit against the
evidence; this module only checks that the typed text is a value at all.
"""

from collections.abc import Mapping
from datetime import date

from reimbursement_council.core.models.claim import FieldEdit
from reimbursement_council.core.models.common import MONEY_FIELDS, FieldName
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
        if not text:
            continue
        value, error = _normalized(field, text)
        if error is not None:
            errors[field] = error
            continue
        read = read_values.get(field)
        if value is not None and value != read:
            edits.append(
                FieldEdit(document_id=primary_id, field=field, read_value=read, typed_value=value)
            )
    return edits, errors
