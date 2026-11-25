"""What a generated prescription or medical report says. Pure: no drawing.

All doctors, diagnoses and names here are made up for synthetic data. The header words match
the kind keywords in config/documents.yaml, so the reader can find the document's type.
"""

import random
from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from reimbursement_council.core.models.common import Model
from reimbursement_council.core.models.reference import PriceListItem
from reimbursement_council.synthetic.receipt_content import PersonName, ProviderProfile

ClinicalKind = Literal["prescription", "medical_report"]

HEADERS: dict[ClinicalKind, tuple[str, str]] = {
    "prescription": ("Prescription", "وصفة طبية"),
    "medical_report": ("Medical Report", "تقرير طبي"),
}
DOCTORS = ("Dr. Huda Salem", "Dr. Fahad Omar", "Dr. Reem Nasser", "Dr. Saad Khalid")
DIAGNOSES = (
    "Upper respiratory infection",
    "Seasonal allergy",
    "Lower back pain",
    "Routine check up",
    "Mild gastritis",
)
DOSES = (
    "1 tablet every 8 hours, 3 days",
    "1 tablet twice a day, 5 days",
    "1 tablet at night, 7 days",
)


class ClinicalDocument(Model):
    kind: ClinicalKind
    provider: ProviderProfile
    patient: PersonName
    issued_at: datetime  # local time, no zone
    doctor: str
    lines: list[str]  # medicines with doses, or the diagnosis and the service
    language: Literal["ar_first", "en_first"]


def make_clinical_document(
    rng: random.Random,
    kind: ClinicalKind,
    provider: ProviderProfile,
    patient: PersonName,
    issued_at: datetime,
    services: Sequence[PriceListItem],
) -> ClinicalDocument:
    """A prescription lists the pharmacy items of the claim; a report names a diagnosis and
    the first service."""
    if kind == "prescription":
        medicines = [s for s in services if s.category == "pharmacy"] or list(services[:1])
        lines = [f"{m.description}, {rng.choice(DOSES)}" for m in medicines]
    else:
        lines = [f"Diagnosis: {rng.choice(DIAGNOSES)}"]
        if services:
            lines.append(f"Service: {services[0].description}")
    return ClinicalDocument(
        kind=kind,
        provider=provider,
        patient=patient,
        issued_at=issued_at,
        doctor=rng.choice(DOCTORS),
        lines=lines,
        language=rng.choice(("ar_first", "en_first")),
    )
