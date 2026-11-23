from reimbursement_council.core.models.claim import ExtractionResult
from reimbursement_council.synthetic.accuracy import FIELDS, compare, summarize
from tests.factories import make_extraction, make_field, make_item

TRUTH = {
    "provider_name": ["Al Noor Clinic", "عيادة النور"],
    "vat_number": "300000000000003",
    "treatment_date": "2026-11-15",
    "invoice_time": "13:30",
    "patient_name": ["Sara Ahmed", "سارة أحمد"],
    "subtotal": "15000",
    "vat_total": "2250",
    "total": "17250",
    "items": [{"service_code": "CONS-GP", "quantity": 1, "amount": 15000}],
    "has_qr": True,
}


def perfect() -> ExtractionResult:
    return make_extraction(
        [
            make_field("provider_name", "عيادة النور", source="qr"),
            make_field("vat_number", "300000000000003"),
            make_field("treatment_date", "2026-11-15"),
            make_field("invoice_timestamp", "2026-11-15T10:30:00Z", source="qr"),
            make_field("patient_name", "sara  ahmed"),
            make_field("subtotal", "15000"),
            make_field("vat_total", "2250"),
            make_field("total", "17250"),
        ],
        [make_item("CONS-GP", 15000)],
    )


def test_perfect_reading_scores_every_field() -> None:
    result = compare(TRUTH, perfect(), qr_found=True)
    assert all(result[field] for field in FIELDS)
    assert result["items"] == (1, 1)


def test_wrong_and_missing_fields() -> None:
    reading = make_extraction([make_field("total", "17200")], [make_item(None, 15000)])
    result = compare(TRUTH, reading, qr_found=False)
    assert result["total"] is False and result["subtotal"] is False and result["qr"] is False
    assert result["items"] == (0, 1)


def test_summary_is_share_correct() -> None:
    rows = [
        compare(TRUTH, perfect(), qr_found=True),
        compare(TRUTH, make_extraction([]), qr_found=True),
    ]
    summary = summarize(rows)
    assert summary["total"] == 0.5 and summary["qr"] == 1.0
    assert summary["item_codes"] == 0.5 and summary["receipts"] == 2
