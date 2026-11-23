"""A claim, its documents, and what we read from them."""

from datetime import date
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from reimbursement_council.core.models.common import (
    MONEY_FIELDS,
    CheckName,
    DocumentKind,
    FieldName,
    FieldSource,
    Halalas,
    Model,
    Score,
)


class Document(Model):
    document_id: str
    claim_id: str
    kind: DocumentKind
    file_path: str
    image_hash: str | None
    uploaded_at: AwareDatetime


class Claim(Model):
    claim_id: str
    member_id: str
    patient_member_id: str
    policy_id: str
    submitted_at: AwareDatetime
    status: str
    documents: list[Document]
    retries_used: int = Field(ge=0)


class FieldLocation(Model):
    page: int = Field(ge=1)
    box: tuple[int, int, int, int]


class ExtractedField(Model):
    """One value read from a document. Money is halalas as digits, dates are YYYY-MM-DD."""

    document_id: str
    name: FieldName
    value: str
    original_text: str
    source: FieldSource
    confidence: Score
    location: FieldLocation | None = None

    @model_validator(mode="after")
    def money_is_halalas_digits(self) -> Self:
        """A reader must hand over money as halalas digits. '22.50' is refused, not guessed."""
        if self.name in MONEY_FIELDS and not (self.value.isascii() and self.value.isdigit()):
            raise ValueError(f"{self.name} must be halalas as digits, got {self.value!r}")
        return self


class LineItem(Model):
    description: str
    service_code: str | None
    quantity: int = Field(ge=1)
    unit_price: Halalas
    amount: Halalas
    confidence: Score


class CheckResult(Model):
    name: CheckName
    passed: bool
    details: str
    fields: list[str]


class ReaderOutput(Model):
    """What a reader returns for one document, before QR merge and checks."""

    fields: list[ExtractedField]
    line_items: list[LineItem]
    qr_payloads: list[str]


class ExtractionResult(Model):
    """One document after QR merge, checks and confidence penalties."""

    document_id: str
    fields: list[ExtractedField]
    line_items: list[LineItem]
    checks: list[CheckResult]

    def all_named(self, name: FieldName) -> list[ExtractedField]:
        return [field for field in self.fields if field.name == name]

    def best(self, name: FieldName) -> ExtractedField | None:
        """The field with this name we are most sure of, or None."""
        candidates = self.all_named(name)
        if not candidates:
            return None
        return max(candidates, key=lambda field: field.confidence)

    def money(self, name: FieldName) -> int | None:
        """The best value as halalas, or None if missing or not digits."""
        if name not in MONEY_FIELDS:
            raise ValueError(f"{name} is not a money field")
        field = self.best(name)
        if field is None or not field.value.isascii() or not field.value.isdigit():
            return None
        return int(field.value)

    def day(self, name: FieldName) -> date | None:
        """The best value as a date (first 10 characters), or None if not a date."""
        field = self.best(name)
        if field is None:
            return None
        try:
            return date.fromisoformat(field.value[:10])
        except ValueError:
            return None
