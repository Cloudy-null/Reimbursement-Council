"""What a generated receipt says, and the true value of every field on it. Pure: no drawing.

All names and VAT numbers here are made up for synthetic data.
"""

import random
import re
from datetime import UTC, datetime, timedelta, timezone
from typing import Literal

from pydantic import Field

from reimbursement_council.core.models.common import Halalas, Model
from reimbursement_council.core.models.reference import PriceListItem
from reimbursement_council.core.money import apply_rate
from reimbursement_council.core.zatca import ZatcaInvoice, encode_zatca_tlv

Layout = Literal["clinic_bilingual", "pharmacy_bilingual", "clinic_arabic_first"]
LAYOUTS: tuple[Layout, ...] = ("clinic_bilingual", "pharmacy_bilingual", "clinic_arabic_first")
ProviderKind = Literal["clinic", "pharmacy", "dental"]
_ARABIC = re.compile("[؀-ۿ]")


class ProviderProfile(Model):
    name_en: str
    name_ar: str
    vat_number: str
    city_en: str
    city_ar: str
    kind: ProviderKind


class PersonName(Model):
    en: str
    ar: str


class PrintedItem(Model):
    service_code: str | None
    description_en: str
    description_ar: str
    quantity: int = Field(ge=1)
    unit_price: Halalas
    amount: Halalas


class ReceiptOptions(Model):
    """Choices for one receipt. None means the generator picks."""

    layout: Layout | None = None
    with_qr: bool = True
    price_factor: float = Field(default=1.0, gt=0)
    unlisted_item: bool = False
    item_count: int | None = Field(default=None, ge=1, le=4)
    issued_at: datetime | None = None  # local time, no zone
    patient: PersonName | None = None
    provider: ProviderProfile | None = None


class ReceiptContent(Model):
    layout: Layout
    provider: ProviderProfile
    invoice_number: str
    issued_at: datetime  # local time, no zone
    patient: PersonName
    file_number: str
    items: list[PrintedItem]
    subtotal: Halalas
    vat_total: Halalas
    total: Halalas
    qr_payload: str | None

    def truth(self) -> dict[str, object]:
        """What a perfect reader returns, in the pipeline's field formats."""
        return {
            "provider_name": [self.provider.name_en, self.provider.name_ar],
            "vat_number": self.provider.vat_number,
            "treatment_date": self.issued_at.date().isoformat(),
            "invoice_time": self.issued_at.strftime("%H:%M"),
            "patient_name": [self.patient.en, self.patient.ar],
            "subtotal": str(self.subtotal),
            "vat_total": str(self.vat_total),
            "total": str(self.total),
            "items": [
                {"service_code": i.service_code, "quantity": i.quantity, "amount": i.amount}
                for i in self.items
            ],
            "has_qr": self.qr_payload is not None,
        }


PROVIDERS: tuple[ProviderProfile, ...] = (
    ProviderProfile(
        name_en="Al Noor Clinic",
        name_ar="عيادة النور",
        vat_number="300000000000003",
        city_en="Riyadh",
        city_ar="الرياض",
        kind="clinic",
    ),
    ProviderProfile(
        name_en="Al Shifa Medical Center",
        name_ar="مركز الشفاء الطبي",
        vat_number="300123456700003",
        city_en="Jeddah",
        city_ar="جدة",
        kind="clinic",
    ),
    ProviderProfile(
        name_en="Green Leaf Pharmacy",
        name_ar="صيدلية الورقة الخضراء",
        vat_number="300765432100003",
        city_en="Dammam",
        city_ar="الدمام",
        kind="pharmacy",
    ),
    ProviderProfile(
        name_en="Al Salam Dental Clinic",
        name_ar="عيادة السلام للأسنان",
        vat_number="300987654300003",
        city_en="Riyadh",
        city_ar="الرياض",
        kind="dental",
    ),
)

PATIENTS: tuple[PersonName, ...] = (
    PersonName(en="Sara Ahmed", ar="سارة أحمد"),
    PersonName(en="Omar Ahmed", ar="عمر أحمد"),
    PersonName(en="Layla Hassan", ar="ليلى حسن"),
    PersonName(en="Khalid Saleh", ar="خالد صالح"),
    PersonName(en="Noura Ali", ar="نورة علي"),
    PersonName(en="Yousef Ibrahim", ar="يوسف إبراهيم"),
)

SERVICES_BY_KIND: dict[ProviderKind, tuple[str, ...]] = {
    "clinic": ("CONS-GP", "CONS-SPEC", "LAB-CBC", "LAB-VITD", "XRAY-CHEST"),
    "pharmacy": ("MED-PARA", "MED-AMOX", "MED-IBU"),
    "dental": ("DENT-CLEAN", "CONS-GP"),
}

UNLISTED_BY_KIND: dict[ProviderKind, tuple[tuple[str, str, int], ...]] = {
    "clinic": (
        ("Physio session", "جلسة علاج طبيعي", 20000),
        ("Nutrition advice", "استشارة تغذية", 18000),
    ),
    "pharmacy": (("Vitamin C tablets", "أقراص فيتامين سي", 2500),),
    "dental": (("Dental x-ray panoramic", "أشعة بانورامية للأسنان", 15000),),
}

LAYOUT_BY_KIND: dict[ProviderKind, tuple[Layout, ...]] = {
    "clinic": ("clinic_bilingual", "clinic_arabic_first"),
    "pharmacy": ("pharmacy_bilingual",),
    "dental": ("clinic_bilingual", "clinic_arabic_first"),
}

SAUDI = timezone(timedelta(hours=3))


def _arabic_name(item: PriceListItem) -> str:
    return next((alias for alias in item.aliases if _ARABIC.search(alias)), item.description)


def make_receipt_content(
    rng: random.Random, prices: dict[str, PriceListItem], options: ReceiptOptions, vat_rate: float
) -> ReceiptContent:
    provider = options.provider or rng.choice(PROVIDERS)
    layout = options.layout or rng.choice(LAYOUT_BY_KIND[provider.kind])
    patient = options.patient or rng.choice(PATIENTS)
    issued_at = options.issued_at or datetime(2026, 11, 1, 8, 0) + timedelta(
        days=rng.randrange(0, 18), minutes=rng.randrange(0, 12 * 60)
    )
    count = options.item_count or rng.randint(1, 3)
    codes = rng.sample(
        SERVICES_BY_KIND[provider.kind], k=min(count, len(SERVICES_BY_KIND[provider.kind]))
    )
    items: list[PrintedItem] = []
    for code in codes:
        price = prices[code]
        quantity = rng.randint(1, 3) if price.category == "pharmacy" else 1
        unit = round(price.network_price * options.price_factor)
        items.append(
            PrintedItem(
                service_code=code,
                description_en=price.description,
                description_ar=_arabic_name(price),
                quantity=quantity,
                unit_price=unit,
                amount=unit * quantity,
            )
        )
    if options.unlisted_item:
        name_en, name_ar, unit = rng.choice(UNLISTED_BY_KIND[provider.kind])
        items.append(
            PrintedItem(
                service_code=None,
                description_en=name_en,
                description_ar=name_ar,
                quantity=1,
                unit_price=unit,
                amount=unit,
            )
        )
    subtotal = sum(item.amount for item in items)
    vat_total = apply_rate(subtotal, vat_rate)
    total = subtotal + vat_total
    qr_payload = None
    if options.with_qr:
        instant = issued_at.replace(tzinfo=SAUDI).astimezone(UTC)
        qr_payload = encode_zatca_tlv(
            ZatcaInvoice(
                seller_name=provider.name_ar,
                vat_number=provider.vat_number,
                timestamp=instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
                total_with_vat=total,
                vat_total=vat_total,
            )
        )
    return ReceiptContent(
        layout=layout,
        provider=provider,
        invoice_number=f"INV-{issued_at:%Y%m%d}-{rng.randrange(1000, 9999)}",
        issued_at=issued_at,
        patient=patient,
        file_number=f"MRN {rng.randrange(100000, 999999)}",
        items=items,
        subtotal=subtotal,
        vat_total=vat_total,
        total=total,
        qr_payload=qr_payload,
    )
