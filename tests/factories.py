"""Small builders for test data. Test-only code, never imported by the package."""

from collections.abc import Sequence

from reimbursement_council.core.models.claim import (
    CheckResult,
    ExtractedField,
    ExtractionResult,
    LineItem,
)
from reimbursement_council.core.models.common import FieldName, FieldSource

DOC_ID = "00000000-0000-4000-8000-0000000000d1"


def make_field(
    name: FieldName,
    value: str,
    confidence: float = 0.95,
    source: FieldSource = "ocr",
) -> ExtractedField:
    return ExtractedField(
        document_id=DOC_ID,
        name=name,
        value=value,
        original_text=value,
        source=source,
        confidence=confidence,
        location=None,
    )


def make_item(
    code: str | None,
    amount: int,
    quantity: int = 1,
    confidence: float = 0.95,
    description: str = "item",
) -> LineItem:
    return LineItem(
        description=description,
        service_code=code,
        quantity=quantity,
        unit_price=amount // quantity,
        amount=amount,
        confidence=confidence,
    )


def make_extraction(
    fields: Sequence[ExtractedField],
    line_items: Sequence[LineItem] = (),
    checks: Sequence[CheckResult] = (),
) -> ExtractionResult:
    return ExtractionResult(
        document_id=DOC_ID,
        fields=list(fields),
        line_items=list(line_items),
        checks=list(checks),
    )
