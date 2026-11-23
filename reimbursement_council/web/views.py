"""Turn decisions and readings into simple rows for the templates. No HTML here."""

from dataclasses import dataclass

from reimbursement_council.core.models.claim import ExtractionResult, LineItem
from reimbursement_council.core.models.decision import PayoutResult
from reimbursement_council.core.money import format_sar

FIELD_ORDER = (
    "provider_name",
    "vat_number",
    "treatment_date",
    "invoice_timestamp",
    "patient_name",
    "subtotal",
    "vat_total",
    "total",
)
MONEY = frozenset({"subtotal", "vat_total", "total"})


@dataclass(frozen=True)
class FieldRow:
    name: str
    value: str
    source: str
    confidence: str
    low: bool


@dataclass(frozen=True)
class MoneyLine:
    label_key: str
    amount: str
    minus: bool


def field_rows(extraction: ExtractionResult | None, floor: float) -> list[FieldRow]:
    if extraction is None:
        return []
    rows = []
    for name in FIELD_ORDER:
        field = extraction.best(name)  # type: ignore[arg-type]
        if field is None:
            continue
        value = (
            format_sar(int(field.value)) if name in MONEY and field.value.isdigit() else field.value
        )
        rows.append(
            FieldRow(
                name=name,
                value=value,
                source=field.source,
                confidence=f"{field.confidence:.2f}",
                low=field.confidence < floor,
            )
        )
    return rows


def payout_lines(payout: PayoutResult | None, items: list[LineItem]) -> list[MoneyLine]:
    """Billed, each cut, and what we pay, so the member sees how the number was made."""
    if payout is None:
        return []
    items_sum = sum(item.amount for item in items)
    receipt_vat = payout.requested - items_sum
    covered = payout.calculated - payout.vat_paid
    unmatched = items_sum - payout.network_cap_cut - payout.copay - payout.limit_cut - covered
    lines = [MoneyLine("billed", format_sar(payout.requested), minus=False)]
    for key, value in (
        ("cap", payout.network_cap_cut),
        ("copay", payout.copay),
        ("limit", payout.limit_cut),
        ("unmatched", unmatched),
        ("vat_diff", receipt_vat - payout.vat_paid),
    ):
        if value > 0:
            lines.append(MoneyLine(key, format_sar(value), minus=True))
    return lines
