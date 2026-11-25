"""The five demo claims: what is in each one. Pure: no drawing, no files.

Each covers one part of the story for the pitch:
- approve: a lab receipt with a QR code. Nothing is missing, so it is approved with no person.
- missing: a pharmacy receipt with no prescription. The member is asked to add it.
- mismatch: a clinic visit whose medical report names another patient. The member is asked.
- edit: a clinic visit with its report. On the check step, change the total: the QR code
  contradicts the typed total, so a person decides, with both values side by side.
- pdf: a lab invoice sent as a PDF, read like a photo.
- optical: an optical shop invoice (synthetic template, never the real file) with frames above
  the yearly frame sub-limit: paid in part, and the check page says why before submit.
- blurry: an Arabic-first clinic receipt photographed out of focus: the system asks for a
  clearer photo instead of guessing.
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
from reimbursement_council.synthetic.optical_content import (
    OpticalInvoice,
    OpticalOptions,
    make_optical_invoice,
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
    optical: OpticalInvoice | None = None
    as_pdf: bool = False
    blur_level: int = 0  # 0 sharp; 1 to 5 out of focus (damage suite, synthetic.yaml)


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


def _optical(issued: datetime, prices: dict[str, PriceListItem]) -> OpticalInvoice:
    """Frames 1,400 SAR and lenses 150 SAR, with the eye test printed and paid by card. The
    frame sub-limit is 1,000 SAR a year, so 400 SAR is over it: a partial payout."""
    options = OpticalOptions(
        lines=[("OPT-FRAME", 140000), ("OPT-LENS", 15000)],
        patient=DEMO_PATIENT,
        issued_at=issued,
        vat_rate=0.0,
    )
    return make_optical_invoice(random.Random(909), prices, options)


def demo_claims(
    issued: datetime, prices: dict[str, PriceListItem], vat_rate: float
) -> dict[str, list[DemoFile]]:
    """The files of each demo claim, all dated `issued` (a few days ago, inside the window)."""
    lab = _receipt(901, 0, ["LAB-CBC"], issued, prices, vat_rate)
    pharmacy = _receipt(902, 2, ["MED-PARA"], issued, prices, vat_rate)
    visit = _receipt(903, 0, ["CONS-GP"], issued, prices, vat_rate)
    edit_visit = _receipt(904, 1, ["CONS-GP"], issued, prices, vat_rate)
    pdf_lab = _receipt(905, 1, ["LAB-VITD"], issued, prices, vat_rate)
    arabic_visit = make_receipt_content(
        random.Random(908),
        prices,
        ReceiptOptions(
            layout="clinic_arabic_first",
            provider=PROVIDERS[0],
            codes=["CONS-SPEC"],
            patient=DEMO_PATIENT,
            issued_at=issued,
        ),
        vat_rate,
    )
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
        "optical": [DemoFile(file_name="invoice.png", optical=_optical(issued, prices))],
        "blurry": [DemoFile(file_name="receipt.png", receipt=arabic_visit, blur_level=4)],
    }


def demo_fixes(issued: datetime, prices: dict[str, PriceListItem]) -> dict[str, list[DemoFile]]:
    """Files the member sends when asked: the mismatch claim's report with the right patient."""
    right = make_clinical_document(
        random.Random(906),
        "medical_report",
        PROVIDERS[0],
        DEMO_PATIENT,
        issued,
        [prices["CONS-GP"]],
    ).model_copy(update={"language": "en_first"})
    return {"mismatch": [DemoFile(file_name="report-right-patient.png", clinical=right)]}
