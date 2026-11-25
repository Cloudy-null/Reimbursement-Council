import random
import re
from datetime import datetime

from reimbursement_council.synthetic.optical_content import (
    SHOPS,
    OpticalInvoice,
    OpticalOptions,
    invoice_sheet,
    make_optical_invoice,
    printed_time,
)
from reimbursement_council.synthetic.optical_documents import (
    eye_test_sheet,
    make_eye_test,
    make_payment_proof,
    payment_sheet,
)
from reimbursement_council.synthetic.receipt_content import PROVIDERS, PersonName
from tests.factories import repo_settings

PATIENT = PersonName(en="Test Person", ar="شخص تجريبي")


def _invoice(seed: int = 1, **changes: object) -> OpticalInvoice:
    options = OpticalOptions(
        lines=[("OPT-FRAME", 160000), ("OPT-LENS", 15000)],
        patient=PATIENT,
        issued_at=datetime(2026, 7, 29, 18, 35),
        vat_rate=0.15,
    ).model_copy(update=changes)
    return make_optical_invoice(random.Random(seed), repo_settings().prices, options)


def test_printed_time_looks_like_the_shop_printer() -> None:
    assert printed_time(datetime(2026, 7, 29, 18, 35)) == "PM 06:35 2026/07/29"
    assert printed_time(datetime(2026, 7, 29, 0, 5)) == "AM 12:05 2026/07/29"


def test_invoice_has_the_key_text() -> None:
    invoice = _invoice()
    text = invoice_sheet(invoice).text()
    for words in (
        "فاتورة ضريبية مبسطة",
        "رقم الفاتورة",
        "التاريخ PM 06:35 2026/07/29",
        "الرقم الضريبي",
        "Barcode الاسم السعر الكمية الاجمالي",
        "اطار نظارة",
        "عدسات طبية",
        "الضريبة (15.0%)",
        "الإجمالي شامل الضريبة 2012.50 ر.س",
        "طريقة الدفع مدى",
        "الوصفة الطبية - شخص تجريبي",
        "EYE SPH CYL Axis ADD",
        "RIGHT",
        "LEFT",
        "IPD",
        "سياسة الاسترجاع",
    ):
        assert words in text, words
    assert re.search(r"رقم الفاتورة \d{13}\n", text)
    vat = re.search(r"الرقم الضريبي (\d+)", text)
    assert vat and len(vat.group(1)) == 15 and vat.group(1)[0] == vat.group(1)[-1] == "3"


def test_every_shop_vat_number_is_15_digits_starting_and_ending_with_3() -> None:
    for shop in SHOPS:
        assert re.fullmatch(r"3\d{13}3", shop.vat_number)


def test_invoice_totals_add_up() -> None:
    invoice = _invoice()
    assert invoice.subtotal == 175000
    assert invoice.vat_total == 26250
    assert invoice.total == 201250


def test_missing_parts_are_not_printed() -> None:
    invoice = _invoice(
        with_invoice_number=False, with_vat_number=False, with_prescription=False, vat_rate=0.0
    )
    text = invoice_sheet(invoice).text()
    assert "رقم الفاتورة" not in text
    assert "الرقم الضريبي" not in text
    assert "الوصفة الطبية" not in text and "EYE" not in text
    assert "الضريبة (0.0%) 0.00 ر.س" in text


def test_payment_words() -> None:
    for method, word in (("tabby", "تابي"), ("credit", "آجل"), ("cash", "نقدا")):
        text = invoice_sheet(_invoice(payment=method)).text()
        assert f"طريقة الدفع {word}" in text


def test_same_seed_same_invoice() -> None:
    assert _invoice(5) == _invoice(5)
    assert _invoice(5) != _invoice(6)


def test_payment_proof_and_eye_test_have_their_type_words() -> None:
    invoice = _invoice()
    proof = make_payment_proof(random.Random(1), invoice)
    assert proof.amount == 201250
    assert "إيصال" in payment_sheet(proof).text()
    eyes = invoice.prescription
    eye_test = make_eye_test(random.Random(1), PROVIDERS[0], invoice.issued_at, eyes)
    text = eye_test_sheet(eye_test).text()
    assert "وصفة طبية" in text and "EYE SPH CYL Axis ADD" in text and PATIENT.ar in text
