import random
from datetime import datetime

from reimbursement_council.core.money import apply_rate
from reimbursement_council.core.zatca import decode_zatca_tlv
from reimbursement_council.synthetic.receipt_content import (
    PROVIDERS,
    ReceiptOptions,
    make_receipt_content,
)
from tests.factories import repo_settings


def make(seed: int = 7, **options: object):  # type: ignore[no-untyped-def]
    settings = repo_settings()
    return make_receipt_content(
        random.Random(seed), settings.prices, ReceiptOptions(**options), settings.policy.vat_rate
    )


def test_totals_add_up_with_15_percent_vat() -> None:
    for seed in range(20):
        receipt = make(seed)
        assert receipt.subtotal == sum(item.amount for item in receipt.items)
        assert receipt.vat_total == apply_rate(receipt.subtotal, 0.15)
        assert receipt.total == receipt.subtotal + receipt.vat_total
        assert all(item.amount == item.unit_price * item.quantity for item in receipt.items)


def test_qr_holds_the_true_values() -> None:
    receipt = make(3, issued_at=datetime(2026, 11, 15, 13, 30))
    assert receipt.qr_payload is not None
    invoice = decode_zatca_tlv(receipt.qr_payload)
    assert invoice is not None
    assert (invoice.vat_number, invoice.total_with_vat, invoice.vat_total) == (
        receipt.provider.vat_number,
        receipt.total,
        receipt.vat_total,
    )
    assert invoice.timestamp == "2026-11-15T10:30:00Z"  # 13:30 in Riyadh


def test_same_seed_same_receipt() -> None:
    assert make(11) == make(11)
    assert make(11) != make(12)


def test_no_qr_and_unlisted_item_options() -> None:
    receipt = make(5, with_qr=False, unlisted_item=True, provider=PROVIDERS[0])
    assert receipt.qr_payload is None
    assert receipt.items[-1].service_code is None
    assert receipt.truth()["has_qr"] is False


def test_price_factor_marks_prices_up() -> None:
    normal = make(9, provider=PROVIDERS[0], item_count=1)
    double = make(9, provider=PROVIDERS[0], item_count=1, price_factor=2.0)
    assert double.items[0].unit_price == 2 * normal.items[0].unit_price


def test_truth_uses_pipeline_formats() -> None:
    truth = make(1, issued_at=datetime(2026, 11, 15, 13, 30)).truth()
    assert truth["treatment_date"] == "2026-11-15" and truth["invoice_time"] == "13:30"
    assert str(truth["total"]).isdigit()
