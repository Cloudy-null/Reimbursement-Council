"""Do the documents of one claim agree on who, when and where? Pure logic, no I/O.

- Patient: each document's patient name is compared with the patient's name on the account,
  in the same script (Arabic with name_ar, Latin with display_name). This avoids comparing an
  Arabic name on a report with an English name on a receipt.
- Dates: every read treatment date must be within date_tolerance_days of the others.
- Provider: only between a medical report and a billing document, and only for the categories
  in provider_check_categories. A prescription from a clinic and a bill from a pharmacy is
  normal, so those are never compared. Names are compared in the same script, like patients:
  the QR gives the Arabic name, a report may be read in English (found in the E12 run).
Missing data gives passed = None ("cannot tell"), never a failure.
"""

from collections.abc import Sequence
from difflib import SequenceMatcher
from itertools import combinations

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import Document, ExtractionResult
from reimbursement_council.core.models.common import BILLING_KINDS, FieldName
from reimbursement_council.core.models.decision import CrossCheckResult
from reimbursement_council.core.models.reference import Member
from reimbursement_council.core.receipt_rows import ARABIC_LETTERS
from reimbursement_council.core.text import normalize_text

DocumentReading = tuple[Document, ExtractionResult]


def _same_name(a: str, b: str, ratio: float) -> bool:
    """Equal after normalizing and sorting the words, or similar enough."""
    left = " ".join(sorted(normalize_text(a).split()))
    right = " ".join(sorted(normalize_text(b).split()))
    if not left or not right:
        return False
    return left == right or SequenceMatcher(None, left, right).ratio() >= ratio


def _value(extraction: ExtractionResult, name: FieldName) -> str | None:
    field = extraction.best(name)
    return None if field is None else field.value


def _patient_check(
    documents: Sequence[DocumentReading], patient: Member, ratio: float
) -> CrossCheckResult:
    compared: list[str] = []
    wrong: list[str] = []
    for document, extraction in documents:
        read = _value(extraction, "patient_name")
        if read is None:
            continue
        account = patient.name_ar if ARABIC_LETTERS.search(read) else patient.display_name
        if account is None:
            continue
        compared.append(document.document_id)
        if not _same_name(read, account, ratio):
            wrong.append(document.document_id)
    if not compared:
        details = "no patient name could be compared with the account"
        return CrossCheckResult(
            name="patient_matches_account",
            passed=None,
            field="patient_name",
            document_ids=[],
            details=details,
        )
    return CrossCheckResult(
        name="patient_matches_account",
        passed=not wrong,
        field="patient_name",
        document_ids=wrong or compared,
        details=(
            f"the patient name on {len(wrong)} document(s) is not the account's patient"
            if wrong
            else "every patient name matches the account"
        ),
    )


def _dates_check(documents: Sequence[DocumentReading], tolerance_days: int) -> CrossCheckResult:
    dated = [
        (document.document_id, day)
        for document, extraction in documents
        if (day := extraction.day("treatment_date")) is not None
    ]
    if len(dated) < 2:
        return CrossCheckResult(
            name="dates_agree",
            passed=None,
            field="treatment_date",
            document_ids=[d for d, _ in dated],
            details="fewer than two documents have a treatment date",
        )
    apart = [
        (a, b)
        for (a, day_a), (b, day_b) in combinations(dated, 2)
        if abs((day_a - day_b).days) > tolerance_days
    ]
    ids = sorted({d for pair in apart for d in pair})
    return CrossCheckResult(
        name="dates_agree",
        passed=not apart,
        field="treatment_date",
        document_ids=ids or [d for d, _ in dated],
        details="treatment dates differ between documents" if apart else "treatment dates agree",
    )


def _same_provider(left: Sequence[str], right: Sequence[str], ratio: float) -> bool | None:
    """Do any two names in the same script match? None when no two share a script."""
    pairs = [
        (a, b)
        for a in left
        for b in right
        if bool(ARABIC_LETTERS.search(a)) == bool(ARABIC_LETTERS.search(b))
    ]
    if not pairs:
        return None
    return any(_same_name(a, b, ratio) for a, b in pairs)


def _providers_check(
    documents: Sequence[DocumentReading], categories: Sequence[str], settings: Settings
) -> CrossCheckResult:
    unknown = CrossCheckResult(
        name="providers_agree",
        passed=None,
        field="provider_name",
        document_ids=[],
        details="providers are not compared for this claim",
    )
    if not set(categories) & set(settings.documents.provider_check_categories):
        return unknown
    named = [
        (document, names)
        for document, extraction in documents
        if (names := [f.value for f in extraction.all_named("provider_name")])
    ]
    reports = [(d, n) for d, n in named if d.kind == "medical_report"]
    bills = [(d, n) for d, n in named if d.kind in BILLING_KINDS]
    ratio = settings.documents.name_match_ratio
    verdicts = [
        (report, bill, verdict)
        for report, report_names in reports
        for bill, bill_names in bills
        if (verdict := _same_provider(report_names, bill_names, ratio)) is not None
    ]
    if not verdicts:
        return unknown
    wrong = sorted(
        {doc.document_id for report, bill, same in verdicts if not same for doc in (report, bill)}
    )
    every = sorted({d.document_id for report, bill, _ in verdicts for d in (report, bill)})
    return CrossCheckResult(
        name="providers_agree",
        passed=not wrong,
        field="provider_name",
        document_ids=wrong or every,
        details="the report and the invoice name different providers"
        if wrong
        else "the report and the invoice name the same provider",
    )


def cross_checks(
    documents: Sequence[DocumentReading],
    patient: Member,
    categories: Sequence[str],
    settings: Settings,
) -> list[CrossCheckResult]:
    config = settings.documents
    return [
        _patient_check(documents, patient, config.name_match_ratio),
        _dates_check(documents, config.date_tolerance_days),
        _providers_check(documents, categories, settings),
    ]
