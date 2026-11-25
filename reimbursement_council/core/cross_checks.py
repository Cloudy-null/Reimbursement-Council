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
from datetime import date
from difflib import SequenceMatcher
from itertools import combinations

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import Document, ExtractionResult
from reimbursement_council.core.models.common import BILLING_KINDS, FieldName
from reimbursement_council.core.models.decision import CrossCheckResult
from reimbursement_council.core.models.reference import Member
from reimbursement_council.core.name_match import is_a_name, same_person
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
    documents: Sequence[DocumentReading], patient: Member, ratio: float, min_confidence: float
) -> CrossCheckResult:
    """A name read below min_confidence, or one that is not a name, cannot tell (web/final:
    every false alarm on the optical set was such a name)."""
    compared: list[str] = []
    wrong: list[str] = []
    for document, extraction in documents:
        field = extraction.best("patient_name")
        if field is None or field.confidence < min_confidence or not is_a_name(field.value):
            continue
        read = field.value
        same_script = patient.name_ar if ARABIC_LETTERS.search(read) else patient.display_name
        accounts = [n for n in (same_script, patient.display_name, patient.name_ar) if n]
        if not accounts:
            continue
        compared.append(document.document_id)
        if not any(same_person(read, account, ratio) for account in accounts):
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


def _dates_check(
    documents: Sequence[DocumentReading], tolerance_days: int, prescription_days: int
) -> CrossCheckResult:
    """A prescription or eye test is written before the purchase: it may be up to
    prescription_days older than the bill (web/final: an eye test 3 days before was an alarm)."""
    dated = [
        (document.document_id, day, document.kind)
        for document, extraction in documents
        if (day := extraction.day("treatment_date")) is not None
    ]
    if len(dated) < 2:
        return CrossCheckResult(
            name="dates_agree",
            passed=None,
            field="treatment_date",
            document_ids=[d for d, _, _ in dated],
            details="fewer than two documents have a treatment date",
        )
    apart = [
        (a, b)
        for (a, day_a, kind_a), (b, day_b, kind_b) in combinations(dated, 2)
        if not _dates_fit(day_a, kind_a, day_b, kind_b, tolerance_days, prescription_days)
    ]
    ids = sorted({d for pair in apart for d in pair})
    return CrossCheckResult(
        name="dates_agree",
        passed=not apart,
        field="treatment_date",
        document_ids=ids or [d for d, _, _ in dated],
        details="treatment dates differ between documents" if apart else "treatment dates agree",
    )


def _dates_fit(
    day_a: date, kind_a: str, day_b: date, kind_b: str, tolerance: int, prescription: int
) -> bool:
    if abs((day_a - day_b).days) <= tolerance:
        return True
    for (rx_day, rx_kind), (bill_day, bill_kind) in (
        ((day_a, kind_a), (day_b, kind_b)),
        ((day_b, kind_b), (day_a, kind_a)),
    ):
        before = (bill_day - rx_day).days
        if rx_kind == "prescription" and bill_kind in BILLING_KINDS and 0 <= before <= prescription:
            return True
    return False


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
        _patient_check(
            documents, patient, config.name_match_ratio, config.patient_name_min_confidence
        ),
        _dates_check(documents, config.date_tolerance_days, config.prescription_before_days),
        _providers_check(documents, categories, settings),
    ]
