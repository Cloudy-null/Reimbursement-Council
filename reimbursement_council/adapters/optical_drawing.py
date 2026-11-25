"""Draw an optical shop invoice, its payment receipt or an eye prescription as a PNG.

The content (what the page says) is built in synthetic/optical_content.py and
synthetic/optical_documents.py as a Sheet; sheet_drawing.py draws it.
"""

from reimbursement_council.adapters.drawing_canvas import Damage, DrawnReceipt
from reimbursement_council.adapters.sheet_drawing import draw_sheet
from reimbursement_council.synthetic.optical_content import OpticalInvoice, invoice_sheet
from reimbursement_council.synthetic.optical_documents import (
    EyeTestDocument,
    PaymentProof,
    eye_test_sheet,
    payment_sheet,
)


def draw_optical_invoice(invoice: OpticalInvoice, damage: Damage | None = None) -> DrawnReceipt:
    return draw_sheet(invoice_sheet(invoice), damage)


def draw_payment_proof(proof: PaymentProof, damage: Damage | None = None) -> DrawnReceipt:
    return draw_sheet(payment_sheet(proof), damage)


def draw_eye_test(document: EyeTestDocument, damage: Damage | None = None) -> DrawnReceipt:
    return draw_sheet(eye_test_sheet(document), damage)
