"""Draw a ReceiptContent as a PNG with Pillow, and optionally damage it like a phone photo.

Arabic is joined with arabic-reshaper and ordered with python-bidi before drawing, so the
image shows real Arabic. Fonts are bundled in assets/fonts so Windows and Linux draw the same.
"""

import io
import re
from functools import cache
from pathlib import Path

import arabic_reshaper
import cv2
import numpy as np
from bidi import get_display
from PIL import Image, ImageDraw, ImageFont
from pydantic import Field

from reimbursement_council.core.models.common import Model
from reimbursement_council.core.money import format_sar
from reimbursement_council.synthetic.receipt_content import Layout, ReceiptContent

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
WIDTH = 760
MARGIN = 40
RIGHT = WIDTH - MARGIN
QTY_X, PRICE_X = 470, 600  # right edges of the quantity and price columns
VALUE_X = 520  # right edge of values in label rows
INK, FAINT, RULE = (20, 20, 20), (105, 105, 105), (190, 190, 190)
_ARABIC = re.compile("[؀-ۿ]")

Box = tuple[int, int, int, int]

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


class Damage(Model):
    """How much to spoil the clean image, like a quick phone photo."""

    blur_sigma: float = Field(default=0.0, ge=0)
    rotate_degrees: float = 0.0
    noise_std: float = Field(default=0.0, ge=0)
    jpeg_quality: int = Field(default=95, ge=10, le=100)
    seed: int = 0


DAMAGE_PRESETS: dict[str, Damage | None] = {
    "none": None,
    "light": Damage(blur_sigma=0.8, rotate_degrees=1.5, noise_std=4.0, jpeg_quality=80),
    "heavy": Damage(blur_sigma=1.4, rotate_degrees=3.0, noise_std=10.0, jpeg_quality=55),
}
"""How hard a generated receipt is spoiled, like a quick or careless phone photo."""


class DrawnReceipt(Model):
    png: bytes
    width: int
    height: int
    boxes: dict[str, list[Box]]


@cache
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "IBMPlexSansArabic-SemiBold.ttf" if bold else "IBMPlexSansArabic-Regular.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), size, layout_engine=ImageFont.Layout.BASIC)


def shape_text(text: str) -> str:
    """Arabic letters joined and put in visual order; other text unchanged."""
    if not _ARABIC.search(text):
        return text
    return str(get_display(arabic_reshaper.reshape(text)))


class _Canvas:
    def __init__(self) -> None:
        self.image = Image.new("RGB", (WIDTH, 2400), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.y = MARGIN
        self.boxes: dict[str, list[Box]] = {}

    def text(
        self,
        x: float,
        text: str,
        size: int,
        *,
        align: str = "left",
        bold: bool = False,
        faint: bool = False,
        field: str | None = None,
    ) -> None:
        font = _font(size, bold)
        shaped = shape_text(text)
        width = self.draw.textlength(shaped, font=font)
        start = x if align == "left" else x - width if align == "right" else x - width / 2
        self.draw.text((start, self.y), shaped, font=font, fill=FAINT if faint else INK)
        if field:
            x0, y0, x1, y1 = self.draw.textbbox((start, self.y), shaped, font=font)
            self.boxes.setdefault(field, []).append((int(x0), int(y0), int(x1) + 1, int(y1) + 1))

    def newline(self, size: int) -> None:
        self.y += int(size * 1.75)

    def rule(self) -> None:
        for x in range(MARGIN, RIGHT, 12):
            self.draw.line((x, self.y, x + 6, self.y), fill=RULE, width=1)
        self.y += 16

    def row(
        self,
        labels: tuple[str, str],
        value: str,
        field: str,
        size: int = 24,
        bold: bool = False,
        arabic_first: bool = False,
    ) -> None:
        english, arabic = labels
        arabic_size = size + 2 if arabic_first else size
        arabic_width = self.draw.textlength(shape_text(arabic), font=_font(arabic_size, bold))
        value_right = min(VALUE_X, RIGHT - arabic_width - 24)  # never touch the Arabic label
        self.text(
            MARGIN, english, size - 4 if arabic_first else size, bold=bold and not arabic_first
        )
        self.text(value_right, value, size, align="right", bold=bold, field=field)
        self.text(RIGHT, arabic, arabic_size, align="right", bold=bold)
        self.newline(size)


def _qr_image(payload: str) -> Image.Image:
    small = cv2.QRCodeEncoder.create().encode(payload)
    big = cv2.resize(small, None, fx=5, fy=5, interpolation=cv2.INTER_NEAREST)
    return Image.fromarray(big).convert("RGB")


def _draw(content: ReceiptContent) -> tuple[Image.Image, dict[str, list[Box]]]:
    labels = LABELS[content.layout]
    arabic_first = content.layout == "clinic_arabic_first"
    c = _Canvas()
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
        format_sar(content.total),
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


def _damage(image: Image.Image, damage: Damage) -> Image.Image:
    pixels = np.array(image)
    if damage.rotate_degrees:
        h, w = pixels.shape[:2]
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), damage.rotate_degrees, 1.0)
        pixels = cv2.warpAffine(pixels, matrix, (w, h), borderValue=(250, 250, 250))
    if damage.blur_sigma:
        pixels = cv2.GaussianBlur(pixels, (0, 0), damage.blur_sigma)
    if damage.noise_std:
        noise = np.random.default_rng(damage.seed).normal(0, damage.noise_std, pixels.shape)
        pixels = np.clip(pixels.astype(np.float64) + noise, 0, 255).astype(np.uint8)
    if damage.jpeg_quality < 95:
        ok, jpeg = cv2.imencode(".jpg", pixels, [cv2.IMWRITE_JPEG_QUALITY, damage.jpeg_quality])
        decoded = cv2.imdecode(jpeg, cv2.IMREAD_COLOR) if ok else None
        if decoded is not None:
            pixels = decoded
    return Image.fromarray(pixels)


def draw_receipt(content: ReceiptContent, damage: Damage | None = None) -> DrawnReceipt:
    image, boxes = _draw(content)
    if damage is not None:
        image = _damage(image, damage)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return DrawnReceipt(png=buffer.getvalue(), width=image.width, height=image.height, boxes=boxes)
