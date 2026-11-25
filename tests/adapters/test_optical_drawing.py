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


def test_the_font_draws_every_letter_of_every_sample() -> None:
    from PIL import ImageFont

    from reimbursement_council.adapters.drawing_canvas import FONT_DIR, shape_text
    from reimbursement_council.synthetic.dental_claims import make_dental_set
    from reimbursement_council.synthetic.language_content import (
        LANGUAGES,
        make_language_receipt,
    )
    from reimbursement_council.synthetic.optical_claims import make_optical_set

    face = ImageFont.truetype(str(FONT_DIR / "IBMPlexSansArabic-Regular.ttf"), 40)
    missing = bytes(face.getmask("￿"))  # the empty box drawn for a letter it lacks
    settings = repo_settings()
    sheets = [d.sheet for c in make_optical_set(1, settings).cases for d in c.documents]
    sheets += [d.sheet for c in make_dental_set(1, settings).cases for d in c.documents]
    for language in LANGUAGES:
        for seed in range(6):
            sheet = make_language_receipt(random.Random(seed), language, settings).sheet
            if sheet is not None:
                sheets.append(sheet)
    letters = {c for sheet in sheets for line in sheet.text().split("\n") for c in shape_text(line)}
    lacking = sorted(
        hex(ord(c)) for c in letters if not c.isspace() and bytes(face.getmask(c)) == missing
    )
    assert lacking == []
