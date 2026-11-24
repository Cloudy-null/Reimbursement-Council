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
