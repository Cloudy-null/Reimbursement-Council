from datetime import UTC, date, datetime

from reimbursement_council.core.cross_checks import cross_checks
from reimbursement_council.core.models.claim import Document, ExtractedField, ExtractionResult
from reimbursement_council.core.models.common import DocumentKind, FieldName
from reimbursement_council.core.models.decision import CrossCheckResult
from reimbursement_council.core.models.reference import Member
from tests.factories import repo_settings


def field_name(name: str) -> FieldName:
    assert name in ("patient_name", "treatment_date", "provider_name")
    return name  # type: ignore[return-value]


OMAR = Member(
    member_id="m1",
    display_name="Omar Ahmed",
    name_ar="عمر أحمد",
    date_joined=date(2023, 1, 1),
    policy_id="p",
)


def doc(document_id: str, kind: DocumentKind, **values: str) -> tuple[Document, ExtractionResult]:
    document = Document(
        document_id=document_id,
        claim_id="c",
        kind=kind,
        file_path=f"{document_id}.png",
        image_hash=None,
        uploaded_at=datetime(2026, 11, 20, tzinfo=UTC),
    )
    fields = [
        ExtractedField(
            document_id=document_id,
            name=field_name(name),
            value=value,
            original_text=value,
            source="ocr",
            confidence=0.95,
        )
        for name, value in values.items()
    ]
    return document, ExtractionResult(
        document_id=document_id, fields=fields, line_items=[], checks=[]
    )


def result(checks: list[CrossCheckResult], name: str) -> CrossCheckResult:
    return next(c for c in checks if c.name == name)


def run(
    *documents: tuple[Document, ExtractionResult], categories: list[str] | None = None
) -> list[CrossCheckResult]:
    return cross_checks(list(documents), OMAR, categories or ["pharmacy"], repo_settings())


def test_always_three_results_in_order() -> None:
    names = [c.name for c in run(doc("r", "receipt"))]
    assert names == ["patient_matches_account", "dates_agree", "providers_agree"]


def test_same_patient_in_arabic_and_english_passes() -> None:
    checks = run(
        doc("r", "receipt", patient_name="Omar Ahmed"),
        doc("p", "prescription", patient_name="عمر أحمد"),
    )
    assert result(checks, "patient_matches_account").passed is True


def test_name_with_letter_forms_case_spaces_and_swapped_order_passes() -> None:
    checks = run(
        doc("r", "receipt", patient_name="AHMED   omar"),
        doc("p", "prescription", patient_name="احمد عمر"),
    )
    assert result(checks, "patient_matches_account").passed is True


def test_other_patient_on_the_prescription_fails_and_names_it() -> None:
    checks = run(
        doc("r", "receipt", patient_name="Omar Ahmed"),
        doc("p", "prescription", patient_name="سارة خالد"),
    )
    check = result(checks, "patient_matches_account")
    assert check.passed is False and check.document_ids == ["p"] and check.field == "patient_name"


def test_dates_one_day_apart_fail_with_zero_tolerance() -> None:
    checks = run(
        doc("r", "receipt", treatment_date="2026-11-20"),
        doc("p", "prescription", treatment_date="2026-11-21"),
    )
    check = result(checks, "dates_agree")
    assert check.passed is False and sorted(check.document_ids) == ["p", "r"]


def test_same_dates_pass() -> None:
    checks = run(
        doc("r", "receipt", treatment_date="2026-11-20"),
        doc("p", "prescription", treatment_date="2026-11-20"),
    )
    assert result(checks, "dates_agree").passed is True


def test_pharmacy_claim_never_compares_providers() -> None:
    checks = run(
        doc("r", "receipt", provider_name="Green Leaf Pharmacy"),
        doc("m", "medical_report", provider_name="Al Noor Clinic"),
    )
    assert result(checks, "providers_agree").passed is None


def test_outpatient_report_from_another_clinic_fails() -> None:
    checks = run(
        doc("i", "invoice", provider_name="Al Noor Clinic"),
        doc("m", "medical_report", provider_name="Al Shifa Medical Center"),
        categories=["outpatient"],
    )
    assert result(checks, "providers_agree").passed is False


def test_outpatient_report_from_the_same_clinic_passes() -> None:
    checks = run(
        doc("i", "invoice", provider_name="Al Noor Clinic"),
        doc("m", "medical_report", provider_name="AL NOOR CLINIC"),
        categories=["outpatient"],
    )
    assert result(checks, "providers_agree").passed is True


def test_nothing_read_gives_unknown_not_fail() -> None:
    checks = run(doc("r", "receipt"), doc("p", "prescription"))
    assert [c.passed for c in checks] == [None, None, None]


def test_no_arabic_name_on_the_account_skips_arabic_names() -> None:
    member = OMAR.model_copy(update={"name_ar": None})
    checks = cross_checks(
        [doc("p", "prescription", patient_name="عمر أحمد")], member, ["pharmacy"], repo_settings()
    )
    assert result(checks, "patient_matches_account").passed is None
