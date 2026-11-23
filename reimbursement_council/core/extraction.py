"""Extraction stage: merge QR and reader fields, run arithmetic and QR checks, lower confidence.

Pure logic. The reader (an adapter) already turned the file into a ReaderOutput.
"""

import logging
from collections.abc import Sequence

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import (
    CheckResult,
    ExtractedField,
    ExtractionResult,
    LineItem,
    ReaderOutput,
)
from reimbursement_council.core.models.common import FieldName
from reimbursement_council.core.money import apply_rate
from reimbursement_council.core.zatca import decode_zatca_tlv

logger = logging.getLogger(__name__)

QR_CONFIDENCE = 1.0
QR_COMPARED: tuple[FieldName, ...] = ("total", "vat_total", "vat_number", "treatment_date")
ITEMS_CHECK = "items_sum_to_subtotal"


def _qr_fields(payloads: Sequence[str], document_id: str) -> list[ExtractedField]:
    """Fields from the first valid ZATCA QR, or none."""
    for payload in payloads:
        invoice = decode_zatca_tlv(payload)
        if invoice is None:
            continue
        values: list[tuple[FieldName, str]] = [
            ("provider_name", invoice.seller_name),
            ("vat_number", invoice.vat_number),
            ("invoice_timestamp", invoice.timestamp),
            ("treatment_date", invoice.timestamp[:10]),
            ("total", str(invoice.total_with_vat)),
            ("vat_total", str(invoice.vat_total)),
        ]
        return [
            ExtractedField(
                document_id=document_id,
                name=name,
                value=value,
                original_text=value,
                source="qr",
                confidence=QR_CONFIDENCE,
            )
            for name, value in values
        ]
    return []


def _best(fields: Sequence[ExtractedField], name: FieldName) -> ExtractedField | None:
    named = [field for field in fields if field.name == name]
    return max(named, key=lambda field: field.confidence) if named else None


def _money(fields: Sequence[ExtractedField], name: FieldName) -> int | None:
    field = _best(fields, name)
    if field is None or not field.value.isascii() or not field.value.isdigit():
        return None
    return int(field.value)


def _merge(
    reader_fields: Sequence[ExtractedField], qr: Sequence[ExtractedField], qr_first: bool
) -> list[ExtractedField]:
    if not qr_first or not qr:
        return list(reader_fields)
    qr_names = {field.name for field in qr}
    return list(qr) + [field for field in reader_fields if field.name not in qr_names]


def _qr_text_check(
    reader_fields: Sequence[ExtractedField], qr: Sequence[ExtractedField]
) -> CheckResult | None:
    """Compare QR values with what the reader printed. Names are never compared (language)."""
    if not qr:
        return None
    compared: list[str] = []
    differing: list[str] = []
    for name in QR_COMPARED:
        qr_field = _best(qr, name)
        printed = _best(reader_fields, name)
        if qr_field is None or printed is None:
            continue
        compared.append(name)
        if printed.value != qr_field.value:
            differing.append(name)
    if not compared:
        return None
    details = (
        f"QR and printed text differ on: {', '.join(differing)}"
        if differing
        else f"QR matches printed text on: {', '.join(compared)}"
    )
    return CheckResult(
        name="qr_matches_text", passed=not differing, details=details, fields=compared
    )


def arithmetic_checks(
    fields: Sequence[ExtractedField],
    line_items: Sequence[LineItem],
    vat_rate: float,
    tolerance: int,
) -> list[CheckResult]:
    """Items add up to subtotal, VAT is the VAT rate, subtotal plus VAT is total.

    A check whose inputs are missing is skipped, not failed.
    """
    subtotal = _money(fields, "subtotal")
    vat_total = _money(fields, "vat_total")
    total = _money(fields, "total")
    checks: list[CheckResult] = []
    if line_items and subtotal is not None:
        items_sum = sum(item.amount for item in line_items)
        checks.append(
            CheckResult(
                name="items_sum_to_subtotal",
                passed=abs(items_sum - subtotal) <= tolerance,
                details=f"items sum {items_sum}, subtotal {subtotal}",
                fields=["subtotal"],
            )
        )
    if subtotal is not None and vat_total is not None and vat_total > 0:
        expected_vat = apply_rate(subtotal, vat_rate)
        checks.append(
            CheckResult(
                name="vat_is_15_percent",
                passed=abs(expected_vat - vat_total) <= tolerance,
                details=f"expected VAT {expected_vat}, receipt VAT {vat_total}",
                fields=["subtotal", "vat_total"],
            )
        )
    if subtotal is not None and vat_total is not None and total is not None:
        checks.append(
            CheckResult(
                name="subtotal_plus_vat_is_total",
                passed=abs(subtotal + vat_total - total) <= tolerance,
                details=f"subtotal {subtotal} plus VAT {vat_total}, total {total}",
                fields=["subtotal", "vat_total", "total"],
            )
        )
    return checks


def _apply_penalties(
    fields: Sequence[ExtractedField],
    line_items: Sequence[LineItem],
    checks: Sequence[CheckResult],
    factor: float,
) -> tuple[list[ExtractedField], list[LineItem]]:
    """Each failed arithmetic check multiplies the confidence of its non-QR fields by factor."""
    failed = [check for check in checks if not check.passed and check.name != "qr_matches_text"]
    new_fields = []
    for field in fields:
        hits = sum(1 for check in failed if field.name in check.fields)
        if field.source == "qr" or hits == 0:
            new_fields.append(field)
        else:
            new_fields.append(
                field.model_copy(update={"confidence": field.confidence * factor**hits})
            )
    items_failed = any(check.name == ITEMS_CHECK for check in failed)
    new_items = [
        item.model_copy(update={"confidence": item.confidence * factor}) if items_failed else item
        for item in line_items
    ]
    return new_fields, new_items


def extract_document(
    document_id: str, reading: ReaderOutput, settings: Settings
) -> ExtractionResult:
    decision = settings.decision
    qr = _qr_fields(reading.qr_payloads, document_id)
    fields = _merge(reading.fields, qr, decision.qr_first_enabled)
    checks: list[CheckResult] = []
    qr_check = _qr_text_check(reading.fields, qr)
    if qr_check is not None:
        checks.append(qr_check)
    if decision.arithmetic_checks_enabled:
        checks += arithmetic_checks(
            fields,
            reading.line_items,
            settings.policy.vat_rate,
            decision.arithmetic_tolerance_halalas,
        )
    fields, items = _apply_penalties(
        fields, reading.line_items, checks, decision.failed_check_confidence_factor
    )
    failed = [check.name for check in checks if not check.passed]
    logger.info(
        "document %s: %d fields, QR %s, failed checks %s",
        document_id,
        len(fields),
        "found" if qr else "none",
        failed or "none",
    )
    return ExtractionResult(document_id=document_id, fields=fields, line_items=items, checks=checks)
