import pytest

from reimbursement_council.core.council import document_checker
from reimbursement_council.core.models.claim import CheckResult, ExtractedField
from reimbursement_council.core.models.decision import Vote
from tests.factories import make_case, make_extraction, make_field, repo_settings

FAILED_CHECK = CheckResult(
    name="vat_is_15_percent", passed=False, details="wrong VAT", fields=["vat_total"]
)


def qr_fields(skip: str = "", date_confidence: float = 1.0) -> list[ExtractedField]:
    fields = [
        make_field("provider_name", "Al Noor Clinic", 1.0, "qr"),
        make_field("treatment_date", "2026-11-15", date_confidence, "qr"),
        make_field("total", "17250", 1.0, "qr"),
    ]
    return [field for field in fields if field.name != skip]


def vote(fields: list[ExtractedField], checks: list[CheckResult] | None = None) -> Vote:
    case = make_case(extraction=make_extraction(fields, checks=checks or []))
    return document_checker.vote(case, repo_settings())


def test_document_all_confident() -> None:
    v = vote(qr_fields())
    assert v.score == 1.0 and v.request is None
    assert v.evidence == ["provider_name", "treatment_date", "total"]


def test_document_missing_total() -> None:
    v = vote(qr_fields(skip="total"))
    assert v.score == pytest.approx(2 / 3)
    assert (v.request_kind, v.request_field) == ("retake_photo", "total")


def test_document_low_date_asks_confirm() -> None:
    v = vote(qr_fields(date_confidence=0.6))
    assert v.score == pytest.approx(2.6 / 3)
    assert (v.request_kind, v.request_field) == ("confirm_field", "treatment_date")


def test_document_failed_check_caps_score() -> None:
    v = vote(qr_fields(), [FAILED_CHECK])
    assert v.score == 0.5
    assert "1 check" in v.reason


def test_document_no_extraction() -> None:
    v = document_checker.vote(make_case(extraction=None), repo_settings())
    assert v.score == 0.0
    assert (v.request_kind, v.request_field) == ("add_document", "receipt")


def test_document_vote_is_named() -> None:
    assert vote(qr_fields()).member == "document_checker"
