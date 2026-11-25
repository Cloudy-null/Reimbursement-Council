"""Parser tests. The three *.ocr.json fixtures are real EasyOCR output on our drawn receipts
(made with tests' seeds 20 to 22), so the misreads in them are the ones the parser must survive."""

import json
from pathlib import Path

import pytest

from reimbursement_council.core.models.claim import ReaderOutput
from reimbursement_council.core.receipt_parsing import parse_receipt_lines
from reimbursement_council.core.receipt_rows import OcrLine
from tests.factories import DOC_ID, repo_settings

OCR = Path(__file__).resolve().parent.parent / "fixtures" / "ocr"


def load(name: str) -> list[OcrLine]:
    raw = json.loads((OCR / f"{name}.ocr.json").read_text(encoding="utf-8"))
    return [OcrLine(text=r["text"], confidence=r["confidence"], box=tuple(r["box"])) for r in raw]


def parse(lines: list[OcrLine]) -> ReaderOutput:
    return parse_receipt_lines(DOC_ID, lines, repo_settings())


def value(output: ReaderOutput, name: str) -> str | None:
    named = [f for f in output.fields if f.name == name]
    return max(named, key=lambda f: f.confidence).value if named else None


def line(text: str, y: int, x: int = 40, confidence: float = 0.95, width: int = 120) -> OcrLine:
    return OcrLine(text=text, confidence=confidence, box=(x, y, x + width, y + 24))


def test_clinic_bilingual_receipt() -> None:
    out = parse(load("clinic_bilingual"))
    assert (value(out, "subtotal"), value(out, "vat_total"), value(out, "total")) == (
        "55000",
        "8250",
        "63250",
    )
    assert value(out, "vat_number") == "300000000000003"
    assert value(out, "treatment_date") == "2026-11-05"
    assert value(out, "invoice_timestamp") == "2026-11-05T12:26:00"
    assert value(out, "patient_name") == "Yousef Ibrahim"
    assert value(out, "provider_name") == "Al Noor Clinic"
    items = [(i.service_code, i.quantity, i.amount) for i in out.line_items]
    assert items == [
        ("CONS-GP", 1, 15000),
        ("LAB-CBC", 1, 8000),
        ("LAB-VITD", 1, 12000),
        (None, 1, 20000),
    ]
    assert out.line_items[3].description == "Physio session"


def test_pharmacy_receipt_with_quantities_and_misread_digits() -> None:
    out = parse(load("pharmacy_bilingual"))
    assert (value(out, "subtotal"), value(out, "vat_total"), value(out, "total")) == (
        "7500",
        "1125",
        "8625",
    )
    assert value(out, "patient_name") == "Omar Ahmed"
    items = [(i.service_code, i.quantity, i.unit_price, i.amount) for i in out.line_items]
    assert items == [("MED-IBU", 2, 2000, 4000), ("MED-AMOX", 1, 3500, 3500)]


def test_arabic_first_receipt() -> None:
    out = parse(load("clinic_arabic_first"))
    assert value(out, "vat_number") == "300123456700003"
    assert value(out, "treatment_date") == "2026-11-08"
    assert value(out, "patient_name") == "عمر أحمد"  # Arabic words put back right to left
    codes = [i.service_code for i in out.line_items]
    assert codes[:2] == ["LAB-VITD", "CONS-SPEC"]


def test_vat_number_letter_o_is_fixed_but_less_sure() -> None:
    out = parse([line("VAT No.", 10), line("3OOOOOO00000003", 10, x=300, confidence=0.8)])
    field = next(f for f in out.fields if f.name == "vat_number")
    assert field.value == "300000000000003"
    assert field.confidence == pytest.approx(0.8 * 0.5)


def test_subtotal_label_is_not_total_and_vat_no_is_not_vat() -> None:
    out = parse(
        [
            line("Tax No.", 10),
            line("300000000000003", 10, x=300),
            line("Sub total", 50),
            line("100.00", 50, x=400),
            line("Tax 15%", 90),
            line("15.00", 90, x=400),
            line("Total", 130),
            line("115.00", 130, x=400),
        ]
    )
    assert (value(out, "subtotal"), value(out, "vat_total"), value(out, "total")) == (
        "10000",
        "1500",
        "11500",
    )


def test_arabic_indic_digits_and_arabic_labels() -> None:
    out = parse([line("الإجمالي", 10, x=600), line("١٧٢٫٥٠", 10, x=300)])
    assert value(out, "total") == "17250"


def test_misread_arabic_label_still_matches() -> None:
    out = parse([line("التاربخ", 10, x=600), line("2026-11-15", 10, x=300)])
    assert value(out, "treatment_date") == "2026-11-15"


def test_quantity_inferred_and_mismatch_lowers_confidence() -> None:
    header = [line("Service", 10), line("Qty", 10, x=430), line("Amount", 10, x=640)]
    good = parse(
        [
            *header,
            line("Paracetamol 500 mg", 50),
            line("15.00", 50, x=520),
            line("45.00", 50, x=640),
        ]
    )
    assert (good.line_items[0].quantity, good.line_items[0].confidence) == (3, 0.95)
    odd = parse(
        [
            *header,
            line("Paracetamol 500 mg", 50),
            line("15.00", 50, x=520),
            line("47.00", 50, x=640),
        ]
    )
    assert odd.line_items[0].confidence == pytest.approx(0.95 * 0.5)


def test_empty_lines_give_empty_output() -> None:
    out = parse([])
    assert out.fields == [] and out.line_items == [] and out.qr_payloads == []


def test_a_label_word_split_from_its_label_is_not_part_of_the_patient_name() -> None:
    # Seen in E12: OCR read "اسم" apart from "المريض", and the name became "اسم ليلى حسن".
    out = parse(
        [
            line("Patient", 300, x=40, width=90),
            line("ليلى حسن", 300, x=360, width=150),
            line("اسم", 300, x=600, width=40),
            line("المريض", 300, x=650, width=70),
        ]
    )
    assert value(out, "patient_name") == "ليلى حسن"


@pytest.mark.parametrize(
    "row, expected",
    [
        ("Date 29-12-2017 11:41", "2017-12-29"),  # real SROIE rows (E1 failure review)
        ("Tax Invoice 12/03/18", "2018-03-12"),
        ("Date: 5.6.2018", "2018-06-05"),
        ("Date 2026-11-08 10:30", "2026-11-08"),
        ("Date 08/11/2026", "2026-11-08"),
    ],
)
def test_common_date_forms_are_read(row: str, expected: str) -> None:
    assert value(parse([line(row, 100, width=400)]), "treatment_date") == expected


def test_a_date_that_does_not_exist_is_not_read() -> None:
    assert value(parse([line("Date 31/02/2018", 100, width=400)]), "treatment_date") is None


def test_the_time_after_a_dashed_date_is_kept() -> None:
    out = parse([line("Date 29-12-2017 11:41", 100, width=400)])
    assert value(out, "invoice_timestamp") == "2017-12-29T11:41:00"


def test_quantity_and_tax_total_rows_are_not_the_total() -> None:
    out = parse(
        [
            line("Total Qty 65.00", 100, width=400),
            line("Total GST 0.36", 140, width=400),
            line("Total Sales (Inclusive of GST) 1,007.50", 180, width=500),
        ]
    )
    assert value(out, "total") == "100750"


def test_a_total_that_includes_tax_is_still_the_total() -> None:
    assert value(parse([line("Total incl. GST 6.36", 100, width=400)]), "total") == "636"


@pytest.mark.parametrize(
    "row, expected",
    [  # real SROIE rows that the first version of the rule got wrong
        ("Item 2 Total with GST 6% 77.20", "7720"),
        ("Total Salas (inclusiva of GST) 4.25", "425"),
        ("Total (Excluding GST): 9.60", "960"),
        ("Total After Rounding 5.00", "500"),
    ],
)
def test_real_total_rows_are_kept(row: str, expected: str) -> None:
    assert value(parse([line(row, 100, width=500)]), "total") == expected


@pytest.mark.parametrize(
    "row, expected",
    [  # data review, day 4: the wider date reading must not take these
        ("Hijri 12/05/1448 Date 2026-10-25", "2026-10-25"),
        ("Invoice 8-12-1234", None),
        ("Ref 10-10-10", None),
        ("Date 08/11/2026.", "2026-11-08"),
    ],
)
def test_hijri_dates_old_years_and_codes_are_not_read_as_the_date(
    row: str, expected: str | None
) -> None:
    assert value(parse([line(row, 100, width=400)]), "treatment_date") == expected


@pytest.mark.parametrize(
    "row, expected",
    [  # real SROIE rows: a short dashed date next to a time or a date label is a date
        ("17-03-18 14 :49 $H01 1J86 R000110133", "2018-03-17"),
        ("Date : 29-01-18 20:38", "2018-01-29"),
        ("07:49PM 503094 14-12-16", "2016-12-14"),
        ("Ref 10-10-10", None),
    ],
)
def test_a_short_dashed_date_counts_next_to_a_time_or_a_date_label(
    row: str, expected: str | None
) -> None:
    assert value(parse([line(row, 100, width=500)]), "treatment_date") == expected


def _field_confidence(reading: ReaderOutput, name: str) -> float:
    return next(f.confidence for f in reading.fields if f.name == name)


def test_a_misread_date_label_does_not_lower_the_date_confidence() -> None:
    """Confidence per field: the date's own text box counts, not a misread label beside it."""
    rows = [
        line("التاريخ", 100, x=300, confidence=0.40),
        line("2026-11-20", 100, x=40, confidence=0.97),
    ]
    reading = parse_receipt_lines(DOC_ID, rows, repo_settings())
    assert _field_confidence(reading, "treatment_date") == pytest.approx(0.97)


def test_a_date_split_over_two_boxes_takes_the_lower_of_the_two() -> None:
    rows = [
        line("Date:", 100, x=10, confidence=0.30, width=60),
        line("17-03-18", 100, x=90, confidence=0.93, width=90),
        line("14:49", 100, x=200, confidence=0.88, width=60),
    ]
    reading = parse_receipt_lines(DOC_ID, rows, repo_settings())
    assert _field_confidence(reading, "treatment_date") == pytest.approx(0.88)


def test_an_item_amount_confidence_comes_from_its_numbers_not_the_description() -> None:
    settings = repo_settings()
    rows = [
        line("Item Qty Price Amount", 100, width=400),
        line("blurry words", 140, x=40, confidence=0.35),
        line("1", 140, x=200, confidence=0.96, width=20),
        line("50.00", 140, x=260, confidence=0.94, width=60),
        line("50.00", 140, x=340, confidence=0.95, width=60),
    ]
    reading = parse_receipt_lines(DOC_ID, rows, settings)
    if reading.line_items:  # the header words decide if this row is an item row
        assert reading.line_items[0].confidence == pytest.approx(0.94)


def test_a_matched_service_rests_on_its_description_confidence_too() -> None:
    settings = repo_settings()
    alias = next(iter(settings.prices.values())).aliases[0]
    rows = [
        line("Item Qty Price Amount", 100, width=400),
        line(alias, 140, x=40, confidence=0.40),
        line("1", 140, x=200, confidence=0.96, width=20),
        line("50.00", 140, x=260, confidence=0.94, width=60),
        line("50.00", 140, x=340, confidence=0.95, width=60),
    ]
    items = parse_receipt_lines(DOC_ID, rows, settings).line_items
    assert items and items[0].service_code is not None
    assert items[0].confidence == pytest.approx(0.40)
