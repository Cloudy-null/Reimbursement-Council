import pytest

from reimbursement_council.core.extraction import arithmetic_checks, extract_document
from reimbursement_council.core.models.claim import ExtractedField, LineItem, ReaderOutput
from reimbursement_council.core.zatca import ZatcaInvoice, encode_zatca_tlv
from tests.factories import DOC_ID, make_field, make_item, repo_settings, settings_with

QR = encode_zatca_tlv(
    ZatcaInvoice(
        seller_name="Al Noor Clinic",
        vat_number="300000000000003",
        timestamp="2026-11-15T10:30:00Z",
        total_with_vat=17250,
        vat_total=2250,
    )
)


def reader_fields(
    subtotal: str = "15000", vat_total: str = "2250", total: str = "17250"
) -> list[ExtractedField]:
    return [
        make_field("provider_name", "Al Noor Clinic"),
        make_field("vat_number", "300000000000003"),
        make_field("treatment_date", "2026-11-15"),
        make_field("subtotal", subtotal),
        make_field("vat_total", vat_total),
        make_field("total", total),
        make_field("patient_name", "Sara Ahmed"),
    ]


ITEMS: list[LineItem] = [make_item("CONS-GP", 15000)]


def reading(
    fields: list[ExtractedField], payloads: list[str], items: list[LineItem] = ITEMS
) -> ReaderOutput:
    return ReaderOutput(fields=fields, line_items=items, qr_payloads=payloads)


def check_map(result_checks: list) -> dict[str, bool]:  # type: ignore[type-arg]
    return {check.name: check.passed for check in result_checks}


def test_qr_fields_win_when_qr_first() -> None:
    result = extract_document(DOC_ID, reading(reader_fields(total="17000"), [QR]), repo_settings())
    total = result.best("total")
    assert total is not None
    assert (total.value, total.source, total.confidence) == ("17250", "qr", 1.0)
    assert result.best("invoice_timestamp") is not None
    qr_check = next(c for c in result.checks if c.name == "qr_matches_text")
    assert qr_check.passed is False and "total" in qr_check.details


def test_reader_fields_when_qr_first_disabled() -> None:
    settings = settings_with(qr_first_enabled=False)
    result = extract_document(DOC_ID, reading(reader_fields(total="17000"), [QR]), settings)
    total = result.best("total")
    assert total is not None and (total.value, total.source) == ("17000", "ocr")
    assert result.best("invoice_timestamp") is None
    assert check_map(result.checks)["qr_matches_text"] is False


def test_bad_qr_payload_ignored() -> None:  # Review Focus 2
    fields = reader_fields()
    result = extract_document(
        DOC_ID, reading(fields, ["https://example.com", "not base64!!"]), repo_settings()
    )
    assert {(f.name, f.value) for f in result.fields} == {(f.name, f.value) for f in fields}
    assert "qr_matches_text" not in check_map(result.checks)


def test_consistent_receipt_passes_all_checks() -> None:
    result = extract_document(DOC_ID, reading(reader_fields(), [QR]), repo_settings())
    assert check_map(result.checks) == {
        "qr_matches_text": True,
        "items_sum_to_subtotal": True,
        "vat_is_15_percent": True,
        "subtotal_plus_vat_is_total": True,
    }
    subtotal = result.best("subtotal")
    assert subtotal is not None and subtotal.confidence == 0.95


def test_wrong_vat_lowers_confidence() -> None:
    fields = reader_fields(subtotal="15000", vat_total="3000", total="18000")
    result = extract_document(DOC_ID, reading(fields, []), repo_settings())
    assert check_map(result.checks) == {
        "items_sum_to_subtotal": True,
        "vat_is_15_percent": False,
        "subtotal_plus_vat_is_total": True,
    }
    vat_total = result.best("vat_total")
    total = result.best("total")
    assert vat_total is not None and vat_total.confidence == pytest.approx(0.95 * 0.5)
    assert total is not None and total.confidence == 0.95


def test_qr_fields_not_penalized() -> None:
    result = extract_document(
        DOC_ID, reading(reader_fields(subtotal="14000"), [QR]), repo_settings()
    )
    checks = check_map(result.checks)
    assert checks["items_sum_to_subtotal"] is False
    assert checks["subtotal_plus_vat_is_total"] is False
    total = result.best("total")
    subtotal = result.best("subtotal")
    assert total is not None and total.confidence == 1.0
    assert subtotal is not None and subtotal.confidence == pytest.approx(0.95 * 0.5**3)
    assert result.line_items[0].confidence == pytest.approx(0.95 * 0.5)


def test_checks_off_when_disabled() -> None:
    settings = settings_with(arithmetic_checks_enabled=False)
    result = extract_document(DOC_ID, reading(reader_fields(subtotal="14000"), [QR]), settings)
    assert set(check_map(result.checks)) == {"qr_matches_text"}
    subtotal = result.best("subtotal")
    assert subtotal is not None and subtotal.confidence == 0.95


def test_no_vat_check_when_vat_is_zero() -> None:
    fields = reader_fields(subtotal="15000", vat_total="0", total="15000")
    result = extract_document(DOC_ID, reading(fields, []), repo_settings())
    assert check_map(result.checks) == {
        "items_sum_to_subtotal": True,
        "subtotal_plus_vat_is_total": True,
    }


def test_arithmetic_checks_skip_missing_inputs() -> None:
    assert arithmetic_checks([make_field("total", "17250")], [], 0.15, 1) == []
    only_subtotal = arithmetic_checks([make_field("subtotal", "15000")], ITEMS, 0.15, 1)
    assert [c.name for c in only_subtotal] == ["items_sum_to_subtotal"]


def test_arithmetic_tolerance_allows_rounding() -> None:
    fields = [make_field("subtotal", "15001"), make_field("vat_total", "2250")]
    checks = arithmetic_checks(fields, [make_item("CONS-GP", 15000)], 0.15, 1)
    assert all(check.passed for check in checks)


def test_qr_treatment_date_is_local() -> None:  # final review: timezone
    late_night = encode_zatca_tlv(
        ZatcaInvoice(
            seller_name="Al Noor Clinic",
            vat_number="300000000000003",
            timestamp="2026-08-21T22:30:00Z",
            total_with_vat=17250,
            vat_total=2250,
        )
    )
    result = extract_document(DOC_ID, reading(reader_fields(), [late_night]), repo_settings())
    treatment = result.best("treatment_date")
    assert treatment is not None and treatment.value == "2026-08-22"


def test_items_checked_against_total_when_no_subtotal() -> None:  # final review: overpayment
    double = [make_item("CONS-GP", 30000, quantity=2)]
    no_subtotal = [f for f in reader_fields() if f.name != "subtotal"]
    checks = arithmetic_checks(no_subtotal, double, 0.15, 1)
    assert check_map(checks)["items_sum_to_subtotal"] is False


def test_items_checked_against_total_when_no_vat_either() -> None:
    total_only = [make_field("total", "15000")]
    assert check_map(arithmetic_checks(total_only, ITEMS, 0.15, 1)) == {
        "items_sum_to_subtotal": True
    }
    vat_unread = [make_field("total", "17250")]
    assert check_map(arithmetic_checks(vat_unread, ITEMS, 0.15, 1)) == {
        "items_sum_to_subtotal": False
    }


def test_passed_checks_corroborate_ocr_money() -> None:  # layer 1: OCR money read at 0.85
    fields = [
        make_field("subtotal", "15000", 0.85),
        make_field("vat_total", "2250", 0.85),
        make_field("total", "17250", 0.85),
    ]
    items = [make_item("CONS-GP", 15000, confidence=0.8)]
    result = extract_document(DOC_ID, reading(fields, [], items), repo_settings())
    for name in ("subtotal", "vat_total", "total"):
        field = result.best(name)
        assert field is not None and field.confidence == 0.95
    assert result.line_items[0].confidence == 0.95


def test_one_failed_check_corroborates_nothing() -> None:
    fields = [
        make_field("subtotal", "15000", 0.85),
        make_field("vat_total", "3000", 0.85),
        make_field("total", "18000", 0.85),
    ]
    result = extract_document(DOC_ID, reading(fields, [], ITEMS), repo_settings())
    total = result.best("total")
    assert total is not None and total.confidence == 0.85
