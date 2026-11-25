"""Receipts in different languages and scripts, for measuring the reader (make-language-set).

Pure: builds the printed sheet and the truth, no drawing. The content comes from the normal
receipt generator (receipt_content.py); only the words, the digits and the date on the page
change. French and Urdu are languages we do not support: the truth says supported false, and
the right outcome for them is to ask for a translation. All names and numbers are made up.
"""

import random
from typing import Literal

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.common import Model
from reimbursement_council.core.money import format_sar
from reimbursement_council.synthetic.hijri import hijri_text
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
from reimbursement_council.synthetic.receipt_content import (
    PersonName,
    ProviderProfile,
    ReceiptContent,
    ReceiptOptions,
    make_receipt_content,
)

Language = Literal[
    "arabic_only",
    "english_only",
    "mixed",
    "arabic_indic_digits",
    "hijri_date",
    "french",
    "urdu",
]
LANGUAGES: tuple[Language, ...] = (
    "arabic_only",
    "english_only",
    "mixed",
    "arabic_indic_digits",
    "hijri_date",
    "french",
    "urdu",
)
SUPPORTED: dict[Language, bool] = {name: name not in ("french", "urdu") for name in LANGUAGES}
ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

FRENCH_CLINIC = ProviderProfile(
    name_en="Clinique Les Oliviers",
    name_ar="Clinique Les Oliviers",
    vat_number="FR00999999990",
    city_en="Lyon",
    city_ar="Lyon",
    kind="clinic",
)
FRENCH_PATIENTS = (
    PersonName(en="Claire Martin", ar="Claire Martin"),
    PersonName(en="Hugo Bernard", ar="Hugo Bernard"),
)
FRENCH_WORDS = {
    "CONS-GP": "Consultation médecin généraliste",
    "CONS-SPEC": "Consultation spécialiste",
    "LAB-CBC": "Analyse de sang (NFS)",
    "LAB-VITD": "Dosage vitamine D",
    "XRAY-CHEST": "Radiographie thoracique",
}
URDU_CLINIC = ProviderProfile(
    name_en="Shifa Clinic",
    name_ar="شفا کلینک",
    vat_number="NTN 0000000-9",
    city_en="Lahore",
    city_ar="لاہور",
    kind="clinic",
)
URDU_PATIENTS = (
    PersonName(en="Ahmed Raza", ar="احمد رضا"),
    PersonName(en="Ayesha Khan", ar="عائشہ خان"),
)
# Only words the bundled font can draw: it has no shapes for ڈ and ڑ, or for ں ے ہ پ standing
# alone, so the Urdu here avoids them (CHECK in the report).
URDU_WORDS = {
    "CONS-GP": "عام معائنہ",
    "CONS-SPEC": "ماہر معائنہ",
    "LAB-CBC": "خون کا ٹیسٹ",
    "LAB-VITD": "وٹامن ٹیسٹ",
    "XRAY-CHEST": "سینے کی تصویر",
}


class LanguageReceipt(Model):
    language: Language
    content: ReceiptContent
    sheet: Sheet | None  # None: drawn with the normal bilingual receipt layout
    hijri: str | None = None  # the Hijri date printed, when there is one

    def truth(self) -> dict[str, object]:
        """read-accuracy's truth format (receipt_content.truth), plus the language keys."""
        extra: dict[str, object] = {
            "damage": "none",
            "layout": self.language,
            "language": self.language,
            "supported": SUPPORTED[self.language],
        }
        if self.hijri is not None:
            extra["hijri_date"] = self.hijri
        return self.content.truth() | extra


def _number(content: ReceiptContent) -> str:
    return content.invoice_number.removeprefix("INV-")


def _arabic_sheet(content: ReceiptContent, date_text: str, digits: bool = False) -> Sheet:
    def value(text: str) -> str:
        return text.translate(ARABIC_INDIC) if digits else text

    rows: list[SheetRow] = [
        title(content.provider.name_ar, field="provider_name"),
        center(content.provider.city_ar),
        heading("فاتورة ضريبية مبسطة"),
        pair("الرقم الضريبي", value(content.provider.vat_number), field="vat_number"),
        rule(),
        pair("رقم الفاتورة", value(_number(content)), field="invoice_number"),
        pair("التاريخ", value(date_text), field="treatment_date"),
        pair("المريض", content.patient.ar, field="patient_name"),
        rule(),
        table_head("الخدمة", "الكمية", "السعر", "المبلغ"),
    ]
    for index, item in enumerate(content.items):
        cells = (str(item.quantity), format_sar(item.unit_price), format_sar(item.amount))
        rows.append(table_row(item.description_ar, *map(value, cells), field=f"item_{index}"))
    rows += [
        rule(),
        pair("المجموع", value(format_sar(content.subtotal)), field="subtotal"),
        pair("ضريبة القيمة المضافة", value(format_sar(content.vat_total)), field="vat_total"),
        pair("الإجمالي", value(format_sar(content.printed_total)), field="total"),
        rule(),
        small("شكرا لزيارتكم"),
    ]
    return Sheet(rows=rows, direction="rtl", page="slip")


def _english_sheet(content: ReceiptContent) -> Sheet:
    rows: list[SheetRow] = [
        title(content.provider.name_en, field="provider_name"),
        center(content.provider.city_en),
        heading("Simplified Tax Invoice"),
        pair("VAT No.", content.provider.vat_number, field="vat_number"),
        rule(),
        pair("Invoice No.", content.invoice_number, field="invoice_number"),
        pair("Date", content.issued_at.strftime("%Y-%m-%d %H:%M"), field="treatment_date"),
        pair("Patient", content.patient.en, field="patient_name"),
        rule(),
        table_head("Service", "Qty", "Price", "Amount"),
    ]
    for index, item in enumerate(content.items):
        rows.append(
            table_row(
                item.description_en,
                str(item.quantity),
                format_sar(item.unit_price),
                format_sar(item.amount),
                field=f"item_{index}",
            )
        )
    rows += [
        rule(),
        pair("Subtotal", format_sar(content.subtotal), field="subtotal"),
        pair("VAT 15%", format_sar(content.vat_total), field="vat_total"),
        pair("Total SAR", format_sar(content.printed_total), field="total"),
        rule(),
        small("Thank you for your visit"),
    ]
    return Sheet(rows=rows, direction="ltr", page="slip")


def _euros(cents: int) -> str:
    return f"{format_sar(cents).replace('.', ',')} EUR"


def _french_sheet(content: ReceiptContent) -> Sheet:
    rows: list[SheetRow] = [
        title(content.provider.name_en, field="provider_name"),
        center(f"12 rue des Lilas, 69003 {content.provider.city_en}"),
        heading("Facture"),
        pair("N° TVA", content.provider.vat_number, field="vat_number"),
        rule(),
        pair("Facture N°", _number(content), field="invoice_number"),
        pair("Date", content.issued_at.strftime("%d/%m/%Y %H:%M"), field="treatment_date"),
        pair("Patient", content.patient.en, field="patient_name"),
        rule(),
        table_head("Désignation", "Qté", "Prix", "Montant"),
    ]
    for index, item in enumerate(content.items):
        rows.append(
            table_row(
                FRENCH_WORDS.get(item.service_code or "", item.description_en),
                str(item.quantity),
                format_sar(item.unit_price).replace(".", ","),
                format_sar(item.amount).replace(".", ","),
                field=f"item_{index}",
            )
        )
    rows += [
        rule(),
        pair("Montant HT", _euros(content.subtotal), field="subtotal"),
        pair("TVA 20%", _euros(content.vat_total), field="vat_total"),
        pair("Total TTC", _euros(content.printed_total), field="total"),
        rule(),
        small("Ordonnance jointe. Merci de votre visite."),
    ]
    return Sheet(rows=rows, direction="ltr", page="slip")


def _urdu_sheet(content: ReceiptContent) -> Sheet:
    rows: list[SheetRow] = [
        title(content.provider.name_ar, field="provider_name"),
        center(content.provider.city_ar),
        heading("رسید"),
        pair("ٹیکس نمبر", content.provider.vat_number, field="vat_number"),
        rule(),
        pair("رسید نمبر", _number(content), field="invoice_number"),
        pair("تاریخ", content.issued_at.strftime("%d-%m-%Y %H:%M"), field="treatment_date"),
        pair("مریض کا نام", content.patient.ar, field="patient_name"),
        rule(),
        table_head("تفصیل", "تعداد", "قیمت", "رقم"),
    ]
    for index, item in enumerate(content.items):
        rows.append(
            table_row(
                URDU_WORDS.get(item.service_code or "", item.description_en),
                str(item.quantity),
                format_sar(item.unit_price),
                format_sar(item.amount),
                field=f"item_{index}",
            )
        )
    rows += [
        rule(),
        pair("رقم", format_sar(content.subtotal), field="subtotal"),
        pair("ٹیکس", format_sar(content.vat_total), field="vat_total"),
        pair("کل رقم", format_sar(content.printed_total), field="total"),
        rule(),
        small("آنے کا شکریہ۔ ہم ہر وقت حاضر ہیں"),
    ]
    return Sheet(rows=rows, direction="rtl", page="slip")


def make_language_receipt(
    rng: random.Random, language: Language, settings: Settings
) -> LanguageReceipt:
    options = ReceiptOptions(with_qr=language == "mixed" and rng.random() < 0.5)
    vat_rate = settings.policy.vat_rate
    if language == "french":
        options = options.model_copy(
            update={"provider": FRENCH_CLINIC, "patient": rng.choice(FRENCH_PATIENTS)}
        )
        vat_rate = 0.20  # French VAT on the page; this receipt is never paid as printed
    elif language == "urdu":
        options = options.model_copy(
            update={"provider": URDU_CLINIC, "patient": rng.choice(URDU_PATIENTS)}
        )
    content = make_receipt_content(rng, settings.prices, options, vat_rate)
    stamp = content.issued_at.strftime("%Y-%m-%d %H:%M")
    if language == "mixed":
        return LanguageReceipt(language=language, content=content, sheet=None)
    if language == "english_only":
        return LanguageReceipt(language=language, content=content, sheet=_english_sheet(content))
    if language == "french":
        return LanguageReceipt(language=language, content=content, sheet=_french_sheet(content))
    if language == "urdu":
        return LanguageReceipt(language=language, content=content, sheet=_urdu_sheet(content))
    if language == "hijri_date":
        hijri = hijri_text(content.issued_at.date())
        # Next to the Gregorian date, or instead of it (then only the time stays).
        printed = (
            f"{stamp} - {hijri} هـ"
            if rng.random() < 0.5
            else f"{hijri} هـ {content.issued_at:%H:%M}"
        )
        sheet = _arabic_sheet(content, printed)
        return LanguageReceipt(language=language, content=content, sheet=sheet, hijri=hijri)
    digits = language == "arabic_indic_digits"
    return LanguageReceipt(
        language=language, content=content, sheet=_arabic_sheet(content, stamp, digits)
    )
