from reimbursement_council.config.models import DocumentsConfig
from reimbursement_council.core.document_kinds import detect_kind
from tests.factories import repo_settings

QR = ["AQ1BbCBOb29yIENsaW5pYw=="]


def cfg() -> DocumentsConfig:
    return repo_settings().documents


def test_qr_means_a_billing_document() -> None:
    assert detect_kind(["Al Noor Clinic", "Total 172.50"], QR, cfg()) == "receipt"


def test_tax_invoice_with_qr_is_an_invoice() -> None:
    assert detect_kind(["فاتورة ضريبية", "عيادة النور"], QR, cfg()) == "invoice"


def test_qr_wins_over_other_keywords() -> None:
    assert detect_kind(["Prescription", "Tax Invoice"], QR, cfg()) == "invoice"


def test_arabic_prescription() -> None:
    assert detect_kind(["وصفة طبية", "المريض: عمر أحمد"], [], cfg()) == "prescription"


def test_english_report_with_an_ocr_typo() -> None:
    assert detect_kind(["MEDICAL REP0RT", "Diagnosis: sprain"], [], cfg()) == "medical_report"


def test_invoice_without_qr() -> None:
    assert detect_kind(["Simplified Tax Invoice", "Total"], [], cfg()) == "invoice"


def test_nothing_known_is_other() -> None:
    assert detect_kind(["hello", "world"], [], cfg()) == "other"


def test_no_text_is_other() -> None:
    assert detect_kind([], [], cfg()) == "other"


def test_a_word_inside_another_word_does_not_count() -> None:
    # "rx" must be a word of its own, not part of "Marx"
    assert detect_kind(["Marx Street"], [], cfg()) == "other"


def test_the_model_type_helps_only_when_keywords_found_nothing() -> None:
    from reimbursement_council.core.document_kinds import kind_with_hint

    assert kind_with_hint("other", "medical_report", has_text=True) == "medical_report"
    assert kind_with_hint("other", "medical_report", has_text=False) == "other"  # blank page
    assert kind_with_hint("receipt", "medical_report", has_text=True) == "receipt"
    assert kind_with_hint("other", None, has_text=True) == "other"
