"""A dental claim set with known right answers (make-dental-claims). Pure: no drawing.

A dental invoice should name the tooth it treated ("رقم السن 14 / Tooth 14"). Half the claims
print it and half do not; those carry the defect missing_tooth_number and should go to
self_fix, where the member sends the clinic's corrected invoice. All names are made up.
"""

import random
from datetime import datetime, timedelta

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import LineItem
from reimbursement_council.core.models.common import DocumentKind, Halalas, Model
from reimbursement_council.core.models.reference import Provider
from reimbursement_council.core.money import apply_rate, format_sar
from reimbursement_council.synthetic.cases import GroundTruth, member_id
from reimbursement_council.synthetic.optical_content import money
from reimbursement_council.synthetic.printed_sheet import (
    Sheet,
    center,
    heading,
    pair,
    rule,
    small,
    table_head,
    table_row,
    title,
)
from reimbursement_council.synthetic.receipt_content import PersonName, ProviderProfile
from reimbursement_council.synthetic.sheet_cases import (
    SheetCase,
    SheetFix,
    SheetSet,
    made_up_people,
    make_claim,
    missing_groups,
    printed_documents,
    sheet_reference,
    truth_payout,
)

DENTAL_POLICY = "00000000-0000-4000-8000-0000000000d1"
FIRST_MEMBER = 200  # member ids 200 and up, apart from the other sets
CLINIC = ProviderProfile(
    name_en="Bright Smile Dental Center",
    name_ar="مركز الابتسامة المشرقة لطب الأسنان",
    vat_number="344444444400003",
    city_en="Riyadh",
    city_ar="الرياض",
    kind="dental",
)
NAMES: dict[str, tuple[str, str]] = {
    "DENT-FILL": ("حشوة سن تجميلية", "Dental filling"),
    "DENT-CLEAN": ("تنظيف اسنان", "Dental cleaning"),
}
# (services with amounts, VAT rate). Each runs once with the tooth number and once without.
VISITS: tuple[tuple[list[tuple[str, Halalas]], float], ...] = (
    ([("DENT-FILL", 35000)], 0.15),
    ([("DENT-FILL", 40000), ("DENT-CLEAN", 25000)], 0.0),
    ([("DENT-CLEAN", 20000)], 0.15),
)


class DentalItem(Model):
    service_code: str
    name_ar: str
    name_en: str
    amount: Halalas


class DentalInvoice(Model):
    clinic: ProviderProfile
    invoice_number: str
    issued_at: datetime
    patient: PersonName
    tooth: int | None  # FDI tooth number, None when not printed
    items: list[DentalItem]
    subtotal: Halalas
    vat_rate: float
    vat_total: Halalas
    total: Halalas

    def truth(self) -> dict[str, object]:
        return {
            "provider_name": [self.clinic.name_en, self.clinic.name_ar],
            "vat_number": self.clinic.vat_number,
            "invoice_number": self.invoice_number,
            "treatment_date": self.issued_at.date().isoformat(),
            "patient_name": [self.patient.en, self.patient.ar],
            "tooth_number": self.tooth,
            "subtotal": str(self.subtotal),
            "vat_total": str(self.vat_total),
            "total": str(self.total),
            "items": [
                {"service_code": i.service_code, "quantity": 1, "amount": i.amount}
                for i in self.items
            ],
        }


def dental_sheet(invoice: DentalInvoice) -> Sheet:
    rows = [
        title(invoice.clinic.name_ar, field="provider_name"),
        center(invoice.clinic.name_en),
        heading("فاتورة ضريبية مبسطة - Simplified Tax Invoice"),
        pair("الرقم الضريبي", invoice.clinic.vat_number, field="vat_number"),
        rule(),
        pair("رقم الفاتورة", invoice.invoice_number, field="invoice_number"),
        pair("التاريخ", invoice.issued_at.strftime("%Y-%m-%d %H:%M"), field="treatment_date"),
        pair("المريض", invoice.patient.ar, field="patient_name"),
    ]
    if invoice.tooth is not None:
        rows.append(pair("رقم السن", f"{invoice.tooth} / Tooth {invoice.tooth}", "tooth_number"))
    rows += [rule(), table_head("الخدمة", "السعر", "الكمية", "الاجمالي")]
    for index, item in enumerate(invoice.items):
        price = format_sar(item.amount)
        rows.append(table_row(item.name_ar, price, "1", price, field=f"item_{index}"))
        rows.append(small(item.name_en))
    rows += [
        rule(),
        pair("المجموع", money(invoice.subtotal), field="subtotal"),
        pair(f"الضريبة ({invoice.vat_rate * 100:.1f}%)", money(invoice.vat_total), "vat_total"),
        pair("الإجمالي", money(invoice.total), field="total"),
        rule(),
        small("شكرا لزيارتكم"),
    ]
    return Sheet(rows=rows, direction="rtl", page="a4")


def make_dental_invoice(
    rng: random.Random,
    lines: list[tuple[str, Halalas]],
    vat_rate: float,
    patient: PersonName,
    issued_at: datetime,
    tooth: int | None,
) -> DentalInvoice:
    items = [
        DentalItem(service_code=code, name_ar=NAMES[code][0], name_en=NAMES[code][1], amount=a)
        for code, a in lines
    ]
    subtotal = sum(i.amount for i in items)
    vat_total = apply_rate(subtotal, vat_rate)
    return DentalInvoice(
        clinic=CLINIC,
        invoice_number=f"DN-{issued_at:%Y%m%d}-{rng.randrange(1000, 9999)}",
        issued_at=issued_at,
        patient=patient,
        tooth=tooth,
        items=items,
        subtotal=subtotal,
        vat_rate=vat_rate,
        vat_total=vat_total,
        total=subtotal + vat_total,
    )


def _case(
    seed: int, index: int, person: PersonName, set_reference: SheetSet, settings: Settings
) -> SheetCase:
    rng = random.Random(seed * 3_000_017 + index)
    lines, vat_rate = VISITS[index // 2]
    with_tooth = index % 2 == 0
    tooth = rng.choice((1, 2, 3, 4)) * 10 + rng.randint(1, 8)  # FDI: quadrant then tooth
    issued = datetime(2026, 9, 1, 9, 0) + timedelta(
        days=rng.randrange(0, 70), minutes=rng.randrange(0, 10 * 60)
    )
    invoice = make_dental_invoice(
        rng, lines, vat_rate, person, issued, tooth if with_tooth else None
    )
    name = f"dental_{seed}_{index:04d}"
    claim_id = f"den-{seed}-{index:04d}"
    sheets: list[tuple[DocumentKind, Sheet]] = [("invoice", dental_sheet(invoice))]
    documents = printed_documents(claim_id, name, sheets)
    member = member_id(FIRST_MEMBER + index)
    submitted = issued + timedelta(days=rng.randint(1, 10))
    claim = make_claim(claim_id, member, DENTAL_POLICY, submitted, documents)
    reference = set_reference.reference
    items = [
        LineItem(
            description=i.name_en,
            service_code=i.service_code,
            quantity=1,
            unit_price=i.amount,
            amount=i.amount,
            confidence=1.0,
        )
        for i in invoice.items
    ]
    groups = [list(g) for g in settings.documents.required_by_category["dental"]]
    truth = GroundTruth(
        should_pay=True,
        correct_payout=truth_payout(
            items,
            invoice.vat_total,
            reference.policy(DENTAL_POLICY),
            reference.history(member),
            settings,
        ),
        defects=[] if with_tooth else ["missing_tooth_number"],
        document_kinds={d.document_id: d.kind for d in documents},
        needs_missing=missing_groups(groups, {d.kind for d in documents}),
        expected_lane=None if with_tooth else "self_fix",
    )
    fix = None
    if not with_tooth:  # the clinic's corrected invoice, with the tooth number
        corrected = invoice.model_copy(update={"tooth": tooth})
        fix = SheetFix(
            file_name=f"{name}-fix.png",
            kind="invoice",
            replace_document_id=documents[0].document_id,
            sheet=dental_sheet(corrected),
        )
    return SheetCase(
        name=name,
        scenario="with_tooth_number" if with_tooth else "missing_tooth_number",
        claim=claim,
        truth=truth,
        documents=documents,
        fields=invoice.truth(),
        fix=fix,
    )


def make_dental_set(seed: int, settings: Settings) -> SheetSet:
    """Six claims: each visit once with the tooth number and once without."""
    count = len(VISITS) * 2
    people = made_up_people(random.Random(seed + 500), count)
    ids = [member_id(FIRST_MEMBER + i) for i in range(count)]
    provider = Provider(
        provider_id="00000000-0000-4000-8000-0000000000d9",
        name=CLINIC.name_en,
        vat_number=CLINIC.vat_number,
        city=CLINIC.city_en,
        in_network=True,
        trust_score=0.8,
    )
    reference = sheet_reference(DENTAL_POLICY, ids, people, [{}] * count, [provider])
    dental = SheetSet(seed=seed, kind="dental", reference=reference)
    cases = [_case(seed, index, people[index], dental, settings) for index in range(count)]
    return dental.model_copy(update={"cases": cases})
