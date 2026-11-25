"""Draw a prescription or a medical report as a PNG, on the same canvas as the receipts.

The header carries the type in English and Arabic so the reader can tell what it is. The
patient, date and provider rows use the same label words as receipts, so the same parser reads
them. Boxes are recorded for patient_name, treatment_date and provider_name.
"""

import io

from reimbursement_council.adapters.drawing_canvas import (
    MARGIN,
    RIGHT,
    WIDTH,
    Canvas,
    Damage,
    DrawnReceipt,
    damage_image,
)
from reimbursement_council.synthetic.document_content import HEADERS, ClinicalDocument


def draw_clinical_document(content: ClinicalDocument, damage: Damage | None = None) -> DrawnReceipt:
    arabic_first = content.language == "ar_first"
    english, arabic = HEADERS[content.kind]
    c = Canvas()
    c.text(
        WIDTH / 2, content.provider.name_ar, 30, align="center", bold=True, field="provider_name"
    )
    c.newline(30)
    c.text(WIDTH / 2, content.provider.name_en, 24, align="center", field="provider_name")
    c.newline(24)
    c.text(
        WIDTH / 2,
        content.provider.city_ar if arabic_first else content.provider.city_en,
        20,
        align="center",
        faint=True,
    )
    c.newline(20)
    c.text(MARGIN, english, 26, bold=not arabic_first)
    c.text(RIGHT, arabic, 28, align="right", bold=True)
    c.newline(28)
    c.rule()
    patient = content.patient.ar if arabic_first else content.patient.en
    c.row(("Patient", "المريض"), patient, "patient_name", 22, arabic_first=arabic_first)
    c.row(
        ("Date", "التاريخ"),
        content.issued_at.strftime("%Y-%m-%d %H:%M"),
        "treatment_date",
        22,
        arabic_first=arabic_first,
    )
    c.row(("Doctor", "الطبيب"), content.doctor, "doctor", 22, arabic_first=arabic_first)
    c.rule()
    for line in content.lines:
        c.text(MARGIN, line, 22)
        c.newline(22)
    c.rule()
    c.text(MARGIN, "Signature and stamp", 18, faint=True)
    c.text(RIGHT, "التوقيع والختم", 18, align="right", faint=True)
    c.newline(18)
    image = c.image.crop((0, 0, WIDTH, c.y + MARGIN))
    if damage is not None:
        image = damage_image(image, damage)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return DrawnReceipt(
        png=buffer.getvalue(), width=image.width, height=image.height, boxes=c.boxes
    )
