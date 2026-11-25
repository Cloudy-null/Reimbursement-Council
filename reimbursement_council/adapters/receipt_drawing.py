"""Draw a ReceiptContent as a PNG with Pillow, and optionally damage it like a phone photo.

The canvas, fonts, Arabic shaping and damage live in drawing_canvas.py, shared with the
prescription and medical report drawing.
"""

import io

import cv2
from PIL import Image

from reimbursement_council.adapters.drawing_canvas import (
    DAMAGE_PRESETS,
    MARGIN,
    RIGHT,
    WIDTH,
    Box,
    Canvas,
    Damage,
    DrawnReceipt,
    damage_image,
    shape_text,
)
from reimbursement_council.core.money import format_sar
from reimbursement_council.synthetic.receipt_content import Layout, ReceiptContent

__all__ = ["DAMAGE_PRESETS", "Damage", "DrawnReceipt", "draw_receipt", "shape_text"]

QTY_X, PRICE_X = 470, 600  # right edges of the quantity and price columns

LABELS: dict[Layout, dict[str, tuple[str, str]]] = {
    "clinic_bilingual": {
        "vat_no": ("VAT No.", "الرقم الضريبي"),
        "title": ("Simplified Tax Invoice", "فاتورة ضريبية مبسطة"),
        "invoice": ("Invoice No.", "رقم الفاتورة"),
        "date": ("Date", "التاريخ"),
        "patient": ("Patient", "المريض"),
        "file": ("File No.", "رقم الملف"),
        "subtotal": ("Subtotal", "المجموع"),
        "vat": ("VAT 15%", "ضريبة القيمة المضافة"),
        "total": ("Total SAR", "الإجمالي"),
        "thanks": ("Thank you for your visit", "شكرا لزيارتكم"),
    },
    "pharmacy_bilingual": {
        "vat_no": ("Tax No.", "الرقم الضريبي"),
        "title": ("Simplified Tax Invoice", "فاتورة ضريبية مبسطة"),
        "invoice": ("Receipt No.", "رقم الإيصال"),
        "date": ("Date", "التاريخ"),
        "patient": ("Customer", "العميل"),
        "subtotal": ("Amount before VAT", "المبلغ قبل الضريبة"),
        "vat": ("VAT amount", "مبلغ الضريبة"),
        "total": ("Grand total", "المجموع الكلي"),
        "thanks": ("Get well soon", "نتمنى لكم الشفاء"),
    },
    "clinic_arabic_first": {
        "vat_no": ("Tax No.", "الرقم الضريبي"),
        "title": ("Tax Invoice", "فاتورة ضريبية مبسطة"),
        "invoice": ("No.", "رقم الفاتورة"),
        "date": ("Date", "التاريخ"),
        "patient": ("Patient", "اسم المريض"),
        "file": ("MRN", "رقم الملف"),
        "subtotal": ("Sub total", "المجموع الفرعي"),
        "vat": ("Tax 15%", "الضريبة"),
        "total": ("Total", "الإجمالي المستحق"),
        "thanks": ("Thank you", "شكرا لكم"),
    },
}


def _qr_image(payload: str) -> Image.Image:
    small = cv2.QRCodeEncoder.create().encode(payload)
    big = cv2.resize(small, None, fx=5, fy=5, interpolation=cv2.INTER_NEAREST)
    return Image.fromarray(big).convert("RGB")


def _draw(content: ReceiptContent) -> tuple[Image.Image, dict[str, list[Box]]]:
    labels = LABELS[content.layout]
    arabic_first = content.layout == "clinic_arabic_first"
    c = Canvas()
    first, second = (content.provider.name_ar, content.provider.name_en)
    c.text(WIDTH / 2, first, 32, align="center", bold=True, field="provider_name")
    c.newline(32)
    c.text(
        WIDTH / 2,
        second,
        26 if not arabic_first else 22,
        align="center",
        bold=not arabic_first,
        field="provider_name",
    )
    c.newline(26)
    c.text(
        WIDTH / 2,
        content.provider.city_ar if arabic_first else content.provider.city_en,
        20,
        align="center",
        faint=True,
    )
    c.newline(20)
    c.row(
        labels["vat_no"], content.provider.vat_number, "vat_number", 22, arabic_first=arabic_first
    )
    c.text(MARGIN, labels["title"][0], 22, bold=not arabic_first)
    c.text(RIGHT, labels["title"][1], 24, align="right", bold=True)
    c.newline(24)
    c.rule()
    c.row(
        labels["invoice"], content.invoice_number, "invoice_number", 22, arabic_first=arabic_first
    )
    c.row(
        labels["date"],
        content.issued_at.strftime("%Y-%m-%d %H:%M"),
        "treatment_date",
        22,
        arabic_first=arabic_first,
    )
    patient = content.patient.ar if arabic_first else content.patient.en
    c.row(labels["patient"], patient, "patient_name", 22, arabic_first=arabic_first)
    if "file" in labels:
        c.row(labels["file"], content.file_number, "file_number", 22, arabic_first=arabic_first)
    c.rule()
    c.text(MARGIN, "الخدمة" if arabic_first else "Service", 20, faint=True)
    c.text(QTY_X, "Qty", 20, align="right", faint=True)
    c.text(PRICE_X, "Price", 20, align="right", faint=True)
    c.text(RIGHT, "Amount", 20, align="right", faint=True)
    c.newline(20)
    for index, item in enumerate(content.items):
        main, other = (
            (item.description_ar, item.description_en)
            if arabic_first
            else (item.description_en, item.description_ar)
        )
        field = f"item_{index}"
        if arabic_first:
            c.text(MARGIN + 260, main, 24, align="right", field=field)
        else:
            c.text(MARGIN, main, 24, field=field)
        c.text(QTY_X, str(item.quantity), 24, align="right", field=field)
        c.text(PRICE_X, format_sar(item.unit_price), 24, align="right", field=field)
        c.text(RIGHT, format_sar(item.amount), 24, align="right", field=field)
        c.newline(24)
        c.text(MARGIN, other, 18, faint=True)
        c.newline(18)
    c.rule()
    c.row(
        labels["subtotal"], format_sar(content.subtotal), "subtotal", 24, arabic_first=arabic_first
    )
    c.row(labels["vat"], format_sar(content.vat_total), "vat_total", 24, arabic_first=arabic_first)
    c.row(
        labels["total"],
        format_sar(content.printed_total),
        "total",
        28,
        bold=True,
        arabic_first=arabic_first,
    )
    c.rule()
    if content.qr_payload:
        qr = _qr_image(content.qr_payload)
        c.image.paste(qr, (MARGIN, c.y))
        c.boxes["qr"] = [(MARGIN, c.y, MARGIN + qr.width, c.y + qr.height)]
        c.y += 20
        c.text(MARGIN + qr.width + 24, labels["thanks"][0], 20, faint=True)
        c.newline(20)
        c.text(MARGIN + qr.width + 24, labels["thanks"][1], 20, faint=True)
        c.y = max(c.y, c.boxes["qr"][0][3] - 20)
    else:
        c.text(MARGIN, labels["thanks"][0], 20, faint=True)
        c.text(RIGHT, labels["thanks"][1], 20, align="right", faint=True)
    c.newline(20)
    height = c.y + MARGIN
    return c.image.crop((0, 0, WIDTH, height)), c.boxes


def draw_receipt(content: ReceiptContent, damage: Damage | None = None) -> DrawnReceipt:
    image, boxes = _draw(content)
    if damage is not None:
        image = damage_image(image, damage)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return DrawnReceipt(png=buffer.getvalue(), width=image.width, height=image.height, boxes=boxes)
