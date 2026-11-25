"""The documents that can go with an optical invoice: a payment receipt (proof that a credit
invoice was paid) and an eye test from a clinic. Pure: no drawing.

Their header words match the kind keywords in config/documents.yaml (إيصال, وصفة طبية), so
the reader can tell their type. All names and numbers are made up.
"""

import random
from datetime import datetime, timedelta

from reimbursement_council.core.models.common import Halalas, Model
from reimbursement_council.synthetic.optical_content import (
    EyePrescription,
    OpticalInvoice,
    eye_rows,
    money,
    printed_time,
)
from reimbursement_council.synthetic.printed_sheet import (
    Sheet,
    center,
    heading,
    pair,
    rule,
    small,
    title,
)
from reimbursement_council.synthetic.receipt_content import ProviderProfile

EYE_DOCTORS = ("د. هدى سالم", "د. سعد خالد", "د. منى العتيبي")


class PaymentProof(Model):
    """A receipt from the shop saying a credit invoice was paid in full."""

    shop_name_ar: str
    receipt_number: str
    invoice_number: str | None
    paid_at: datetime  # local time, no zone
    amount: Halalas
    method_ar: str


class EyeTestDocument(Model):
    """An eye test (prescription for glasses) from a clinic, as its own document."""

    clinic: ProviderProfile
    issued_at: datetime
    doctor: str
    eyes: EyePrescription


def make_payment_proof(rng: random.Random, invoice: OpticalInvoice) -> PaymentProof:
    return PaymentProof(
        shop_name_ar=invoice.shop.name_ar,
        receipt_number=f"RC-{rng.randrange(100000, 999999)}",
        invoice_number=invoice.invoice_number,
        paid_at=invoice.issued_at + timedelta(days=rng.randint(3, 20), hours=rng.randint(0, 5)),
        amount=invoice.total,
        method_ar=rng.choice(("تحويل بنكي", "مدى", "نقدا")),
    )


def make_eye_test(
    rng: random.Random, clinic: ProviderProfile, invoice_time: datetime, eyes: EyePrescription
) -> EyeTestDocument:
    return EyeTestDocument(
        clinic=clinic,
        issued_at=invoice_time - timedelta(minutes=rng.randint(10, 300)),  # same day
        doctor=rng.choice(EYE_DOCTORS),
        eyes=eyes,
    )


def payment_sheet(proof: PaymentProof) -> Sheet:
    rows = [
        title(proof.shop_name_ar, field="provider_name"),
        heading("إيصال سداد - سند قبض"),
        center("Payment Receipt"),
        rule(),
        pair("رقم الإيصال", proof.receipt_number),
        pair("عن الفاتورة رقم", proof.invoice_number or "-"),
        pair("تاريخ السداد", printed_time(proof.paid_at), field="payment_date"),
        pair("المبلغ المدفوع", money(proof.amount), field="total"),
        pair("طريقة الدفع", proof.method_ar),
        rule(),
        small("تم استلام المبلغ أعلاه وسداد الفاتورة بالكامل."),
    ]
    return Sheet(rows=rows, direction="rtl", page="slip")


def eye_test_sheet(document: EyeTestDocument) -> Sheet:
    rows = [
        title(document.clinic.name_ar, field="provider_name"),
        center(document.clinic.name_en),
        heading("وصفة طبية - Prescription"),
        center("فحص النظر - Eye test"),
        rule(),
        pair("المريض", document.eyes.patient.ar, field="patient_name"),
        pair("التاريخ", document.issued_at.strftime("%Y-%m-%d %H:%M"), field="treatment_date"),
        pair("الطبيب", document.doctor),
        rule(),
        *eye_rows(document.eyes),
        rule(),
        small("التوقيع والختم"),
    ]
    return Sheet(rows=rows, direction="rtl", page="slip")
