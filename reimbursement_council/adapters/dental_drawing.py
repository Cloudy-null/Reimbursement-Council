"""Draw a dental invoice as a PNG. The content is built in synthetic/dental_claims.py as a
Sheet; sheet_drawing.py draws it."""

from reimbursement_council.adapters.drawing_canvas import Damage, DrawnReceipt
from reimbursement_council.adapters.sheet_drawing import draw_sheet
from reimbursement_council.synthetic.dental_claims import DentalInvoice, dental_sheet


def draw_dental_invoice(invoice: DentalInvoice, damage: Damage | None = None) -> DrawnReceipt:
    return draw_sheet(dental_sheet(invoice), damage)
