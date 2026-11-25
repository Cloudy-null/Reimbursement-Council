"""What a generated optical shop invoice says, and the true value of every field. Pure.

The layout follows a simplified tax invoice from a Saudi optical shop: mostly Arabic, a
13 digit invoice number, the date printed as "PM 06:35 2026/07/29", an items table with a
barcode column, totals in ر.س, the payment method, and sometimes the eye prescription printed
on the invoice. All shops, people, phone numbers and VAT numbers here are made up.
"""

import random
from datetime import datetime
from typing import Literal

from pydantic import Field

from reimbursement_council.core.models.common import Halalas, Model
from reimbursement_council.core.models.reference import PriceListItem
from reimbursement_council.core.money import apply_rate, format_sar
from reimbursement_council.synthetic.printed_sheet import (
    Sheet,
    SheetRow,
    center,
    heading,
    pair,
    rule,
    small,
    table_head,
    table_row,
    title,
)
from reimbursement_council.synthetic.receipt_content import PersonName, arabic_name

PaymentMethod = Literal["mada", "cash", "tabby", "credit"]
# How each payment method is printed. Tabby is a pay later service; آجل is a credit invoice.
PAYMENT_WORDS: dict[PaymentMethod, str] = {
    "mada": "مدى",
    "cash": "نقدا",
    "tabby": "تابي",
    "credit": "آجل",
}
SAR = "ر.س"


class OpticalShop(Model):
    name_ar: str
    name_en: str
    address_ar: str
    phone: str
    vat_number: str  # 15 digits, starts and ends with 3 (made up)
    city_en: str


SHOPS: tuple[OpticalShop, ...] = (
    OpticalShop(
        name_ar="بصريات الأفق",
        name_en="Al Ofuq Optics",
        address_ar="الرياض - حي النخيل - طريق الملك فهد",
        phone="0115550142",
        vat_number="311111111100003",
        city_en="Riyadh",
    ),
    OpticalShop(
        name_ar="نور البصر للنظارات",
        name_en="Noor Al Basar Eyewear",
        address_ar="جدة - حي الروضة - شارع صاري",
        phone="0125550178",
        vat_number="322222222200003",
        city_en="Jeddah",
    ),
    OpticalShop(
        name_ar="مركز الرؤية الواضحة للبصريات",
        name_en="Clear Vision Optical Center",
        address_ar="الدمام - حي الشاطئ - شارع الخليج",
        phone="0135550113",
        vat_number="333333333300003",
        city_en="Dammam",
    ),
)
SALESPEOPLE = ("محمد سعيد", "أحمد خالد", "فيصل عمر", "ريم عبدالله")
# Made-up model words after the generic word, so the service can still be matched.
DETAILS: dict[str, tuple[str, ...]] = {
    "OPT-FRAME": ("لونا 52", "سيرا معدني", "فيستا كلاسيك", "ماركو خفيف"),
    "OPT-LENS": ("مضادة للانعكاس", "فوتوكروميك", "رقيقة 1.67", "حماية الضوء الأزرق"),
    "OPT-EXAM": ("شامل",),
}
RETURNS_POLICY = (
    "سياسة الاسترجاع: يمكن استبدال الإطار خلال 7 أيام مع الفاتورة الأصلية. "
    "العدسات الطبية المصنوعة حسب الوصفة لا ترد ولا تستبدل."
)


class OpticalItem(Model):
    barcode: str
    service_code: str
    name_ar: str
    quantity: int = Field(ge=1)
    unit_price: Halalas
    amount: Halalas


class EyeValues(Model):
    sph: float
    cyl: float
    axis: int = Field(ge=0, le=180)
    add: float


class EyePrescription(Model):
    patient: PersonName
    right: EyeValues
    left: EyeValues
    ipd: int  # distance between the pupils, in millimetres


class OpticalOptions(Model):
    """Choices for one invoice. Prices are given, so the right payout is known."""

    lines: list[tuple[str, Halalas]]  # (service code, amount) in print order
    patient: PersonName
    issued_at: datetime  # local time, no zone
    vat_rate: float = Field(ge=0, le=1)
    payment: PaymentMethod = "mada"
    with_prescription: bool = True
    with_invoice_number: bool = True
    with_vat_number: bool = True
    shop: OpticalShop | None = None


class OpticalInvoice(Model):
    shop: OpticalShop
    invoice_number: str | None
    issued_at: datetime
    vat_number: str | None  # None: the shop's VAT number is not printed
    salesperson: str
    items: list[OpticalItem]
    subtotal: Halalas
    vat_rate: float
    vat_total: Halalas
    total: Halalas
    payment: PaymentMethod
    prescription: EyePrescription | None

    def truth(self) -> dict[str, object]:
        """What a perfect reader returns, in the pipeline's field formats."""
        return {
            "provider_name": [self.shop.name_en, self.shop.name_ar],
            "vat_number": self.vat_number,
            "invoice_number": self.invoice_number,
            "treatment_date": self.issued_at.date().isoformat(),
            "invoice_time": self.issued_at.strftime("%H:%M"),
            "subtotal": str(self.subtotal),
            "vat_total": str(self.vat_total),
            "total": str(self.total),
            "items": [
                {"service_code": i.service_code, "quantity": i.quantity, "amount": i.amount}
                for i in self.items
            ],
            "payment_method": self.payment,
            "prescription_on_invoice": self.prescription is not None,
        }


def printed_time(moment: datetime) -> str:
    """'PM 06:35 2026/07/29', as the shop's printer puts it (no locale needed)."""
    half = "PM" if moment.hour >= 12 else "AM"
    hour = moment.hour % 12 or 12
    return f"{half} {hour:02d}:{moment.minute:02d} {moment:%Y/%m/%d}"


def money(halalas: int) -> str:
    return f"{format_sar(halalas)} {SAR}"


def _eye(rng: random.Random) -> EyeValues:
    return EyeValues(
        sph=rng.randrange(-32, 13) * 0.25,
        cyl=-rng.randrange(0, 9) * 0.25,
        axis=rng.randrange(0, 181, 5),
        add=rng.choice((0.0, 0.0, 1.0, 1.5, 2.0)),
    )


def make_optical_invoice(
    rng: random.Random, prices: dict[str, PriceListItem], options: OpticalOptions
) -> OpticalInvoice:
    shop = options.shop or rng.choice(SHOPS)
    items = [
        OpticalItem(
            barcode="".join(str(rng.randrange(10)) for _ in range(13)),
            service_code=code,
            name_ar=f"{arabic_name(prices[code])} {rng.choice(DETAILS[code])}",
            quantity=1,
            unit_price=amount,
            amount=amount,
        )
        for code, amount in options.lines
    ]
    subtotal = sum(item.amount for item in items)
    vat_total = apply_rate(subtotal, options.vat_rate)
    prescription = None
    if options.with_prescription:
        prescription = EyePrescription(
            patient=options.patient, right=_eye(rng), left=_eye(rng), ipd=rng.randint(56, 70)
        )
    number = "".join(str(rng.randrange(10)) for _ in range(13))
    return OpticalInvoice(
        shop=shop,
        invoice_number=number if options.with_invoice_number else None,
        issued_at=options.issued_at,
        vat_number=shop.vat_number if options.with_vat_number else None,
        salesperson=rng.choice(SALESPEOPLE),
        items=items,
        subtotal=subtotal,
        vat_rate=options.vat_rate,
        vat_total=vat_total,
        total=subtotal + vat_total,
        payment=options.payment,
        prescription=prescription,
    )


def eye_rows(prescription: EyePrescription) -> list[SheetRow]:
    """The small eye table, left to right: EYE SPH CYL Axis ADD, RIGHT and LEFT, then IPD."""
    rows = [table_head("EYE", "SPH", "CYL", "Axis", "ADD", direction="ltr")]
    for side, eye in (("RIGHT", prescription.right), ("LEFT", prescription.left)):
        cells = (side, f"{eye.sph:.2f}", f"{eye.cyl:.2f}", str(eye.axis), f"{eye.add:.2f}")
        rows.append(table_row(*cells, direction="ltr"))
    rows.append(table_row("IPD", str(prescription.ipd), direction="ltr"))
    return rows


def invoice_sheet(invoice: OpticalInvoice) -> Sheet:
    """The invoice as printed rows, top to bottom."""
    shop = invoice.shop
    rows = [
        title(shop.name_ar, field="provider_name"),
        heading("فاتورة ضريبية مبسطة"),
        center(shop.address_ar),
        center(f"هاتف: {shop.phone}"),
        rule(),
    ]
    if invoice.invoice_number is not None:
        rows.append(pair("رقم الفاتورة", invoice.invoice_number, field="invoice_number"))
    rows.append(pair("التاريخ", printed_time(invoice.issued_at), field="treatment_date"))
    if invoice.vat_number is not None:
        rows.append(pair("الرقم الضريبي", invoice.vat_number, field="vat_number"))
    rows += [pair("البائع", invoice.salesperson), rule()]
    rows.append(table_head("Barcode", "الاسم", "السعر", "الكمية", "الاجمالي"))
    for index, item in enumerate(invoice.items):
        rows.append(
            table_row(
                item.barcode,
                item.name_ar,
                format_sar(item.unit_price),
                str(item.quantity),
                format_sar(item.amount),
                field=f"item_{index}",
            )
        )
    rows += [
        rule(),
        pair("الاجمالي", money(invoice.subtotal), field="subtotal"),
        pair(f"الضريبة ({invoice.vat_rate * 100:.1f}%)", money(invoice.vat_total), "vat_total"),
        pair("الإجمالي شامل الضريبة", money(invoice.total), field="total"),
        pair("طريقة الدفع", PAYMENT_WORDS[invoice.payment], field="payment_method"),
    ]
    if invoice.prescription is not None:
        rows += [rule(), heading(f"الوصفة الطبية - {invoice.prescription.patient.ar}")]
        rows += eye_rows(invoice.prescription)
    rows += [rule(), small(RETURNS_POLICY)]
    return Sheet(rows=rows, direction="rtl", page="a4")
