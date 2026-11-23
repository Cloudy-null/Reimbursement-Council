"""Small builders for test data. Test-only code, never imported by the package."""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from functools import cache
from pathlib import Path
from typing import Any, Literal

from reimbursement_council.config.loader import load_settings
from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import (
    CheckResult,
    Claim,
    Document,
    ExtractedField,
    ExtractionResult,
    LineItem,
)
from reimbursement_council.core.models.common import FieldName, FieldSource
from reimbursement_council.core.models.reference import Policy

DOC_ID = "00000000-0000-4000-8000-0000000000d1"
CLAIM_ID = "00000000-0000-4000-8000-0000000000c1"
MEMBER_ID = "00000000-0000-4000-8000-0000000000a1"
POLICY_ID = "00000000-0000-4000-8000-0000000000b1"
SUBMITTED_AT = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
REPO_CONFIG = Path(__file__).resolve().parent.parent / "config"


def make_claim(
    submitted_at: datetime = SUBMITTED_AT,
    patient_member_id: str = MEMBER_ID,
    retries_used: int = 0,
    claim_id: str = CLAIM_ID,
) -> Claim:
    return Claim(
        claim_id=claim_id,
        member_id=MEMBER_ID,
        patient_member_id=patient_member_id,
        policy_id=POLICY_ID,
        submitted_at=submitted_at,
        status="submitted",
        documents=[
            Document(
                document_id=DOC_ID,
                claim_id=claim_id,
                kind="receipt",
                file_path="receipt.reading.json",
                image_hash="hash-1",
                uploaded_at=submitted_at,
            )
        ],
        retries_used=retries_used,
    )


def make_policy(
    start_date: date = date(2026, 1, 1),
    end_date: date = date(2026, 12, 31),
    status: Literal["active", "inactive"] = "active",
) -> Policy:
    return Policy(
        policy_id=POLICY_ID,
        tier="silver",
        start_date=start_date,
        end_date=end_date,
        status=status,
        covered_people=[MEMBER_ID],
    )


@cache
def repo_settings() -> Settings:
    return load_settings(REPO_CONFIG, env={})


def settings_with(**decision_changes: Any) -> Settings:
    """The repo settings with some decision.yaml values changed (not re-validated)."""
    settings = repo_settings()
    decision = settings.decision.model_copy(update=decision_changes)
    return settings.model_copy(update={"decision": decision})


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
