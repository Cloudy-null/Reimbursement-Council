import io
import random
from datetime import datetime

from PIL import Image

from reimbursement_council.adapters.optical_drawing import draw_optical_invoice
from reimbursement_council.adapters.sheet_drawing import A4_HEIGHT, draw_sheet
from reimbursement_council.synthetic.optical_content import (
    OpticalInvoice,
    OpticalOptions,
    make_optical_invoice,
)
from reimbursement_council.synthetic.printed_sheet import Sheet, pair, small
from reimbursement_council.synthetic.receipt_content import PersonName
from tests.factories import repo_settings


def _invoice(seed: int) -> OpticalInvoice:
    options = OpticalOptions(
        lines=[("OPT-FRAME", 90000), ("OPT-LENS", 50000)],
        patient=PersonName(en="Test Person", ar="شخص تجريبي"),
        issued_at=datetime(2026, 9, 2, 10, 15),
        vat_rate=0.15,
    )
    return make_optical_invoice(random.Random(seed), repo_settings().prices, options)


def test_optical_invoice_draws_the_same_for_a_seed() -> None:
    first = draw_optical_invoice(_invoice(3))
    again = draw_optical_invoice(_invoice(3))
    assert first.png == again.png
    assert first.height >= A4_HEIGHT > first.width  # portrait page
    assert {"provider_name", "invoice_number", "vat_number", "total", "item_0"} <= set(first.boxes)
    image = Image.open(io.BytesIO(first.png))
    assert image.size == (first.width, first.height)


def test_long_small_print_wraps_and_slip_pages_are_short() -> None:
    sheet = Sheet(rows=[pair("الاسم", "قيمة"), small("كلمة " * 120)], page="slip")
    drawn = draw_sheet(sheet)
    assert drawn.height < A4_HEIGHT
    assert drawn.height > 100  # several wrapped lines
