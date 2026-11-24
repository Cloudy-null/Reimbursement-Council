"""The five demo claims: what is in each one. Pure: no drawing, no files.

Each covers one part of the story for the pitch:
- approve: a lab receipt with a QR code. Nothing is missing, so it is approved with no person.
- missing: a pharmacy receipt with no prescription. The member is asked to add it.
- mismatch: a clinic visit whose medical report names another patient. The member is asked.
- edit: a clinic visit with its report. On the check step, change the total: the QR code
  contradicts the typed total, so a person decides, with both values side by side.
- pdf: a lab invoice sent as a PDF, read like a photo.
All people and clinics are made up. The patient is the first person in the form list.
"""

import random
from datetime import datetime

from reimbursement_council.core.models.common import Model
from reimbursement_council.core.models.reference import PriceListItem
from reimbursement_council.synthetic.document_content import (
    ClinicalDocument,
    make_clinical_document,
)
from reimbursement_council.synthetic.receipt_content import (
    PATIENTS,
    PROVIDERS,
    ReceiptContent,
    ReceiptOptions,
    make_receipt_content,
)

DEMO_PATIENT = PATIENTS[0]


class DemoFile(Model):
    file_name: str
    receipt: ReceiptContent | None = None
    clinical: ClinicalDocument | None = None
    as_pdf: bool = False


def _receipt(
    seed: int,
    provider_index: int,
    codes: list[str],
    issued: datetime,
    prices: dict[str, PriceListItem],
    vat_rate: float,
) -> ReceiptContent:
    options = ReceiptOptions(
        provider=PROVIDERS[provider_index], codes=codes, patient=DEMO_PATIENT, issued_at=issued
    )
    return make_receipt_content(random.Random(seed), prices, options, vat_rate)


def demo_claims(
    issued: datetime, prices: dict[str, PriceListItem], vat_rate: float
) -> dict[str, list[DemoFile]]:
    """The files of each demo claim, all dated `issued` (a few days ago, inside the window)."""
    lab = _receipt(901, 0, ["LAB-CBC"], issued, prices, vat_rate)
    pharmacy = _receipt(902, 2, ["MED-PARA"], issued, prices, vat_rate)
    visit = _receipt(903, 0, ["CONS-GP"], issued, prices, vat_rate)
    edit_visit = _receipt(904, 1, ["CONS-GP"], issued, prices, vat_rate)
    pdf_lab = _receipt(905, 1, ["LAB-VITD"], issued, prices, vat_rate)
    gp = [prices["CONS-GP"]]
    wrong_patient = make_clinical_document(
        random.Random(906), "medical_report", PROVIDERS[0], PATIENTS[1], issued, gp
    ).model_copy(update={"language": "en_first"})
    right_report = make_clinical_document(
        random.Random(907), "medical_report", PROVIDERS[1], DEMO_PATIENT, issued, gp
    ).model_copy(update={"language": "en_first"})
    return {
        "approve": [DemoFile(file_name="receipt.png", receipt=lab)],
        "missing": [DemoFile(file_name="receipt.png", receipt=pharmacy)],
        "mismatch": [
            DemoFile(file_name="receipt.png", receipt=visit),
            DemoFile(file_name="report.png", clinical=wrong_patient),
        ],
        "edit": [
            DemoFile(file_name="receipt.png", receipt=edit_visit),
            DemoFile(file_name="report.png", clinical=right_report),
        ],
        "pdf": [DemoFile(file_name="invoice.pdf", receipt=pdf_lab, as_pdf=True)],
    }
