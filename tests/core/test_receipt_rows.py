"""Row grouping tests: which OCR boxes form one row, and the order a row is read in."""

from reimbursement_council.core.receipt_rows import OcrLine, group_rows, join_row


def line(text: str, y: int, x: int = 40, confidence: float = 0.95, width: int = 120) -> OcrLine:
    return OcrLine(text=text, confidence=confidence, box=(x, y, x + width, y + 24))


def test_rows_group_by_height() -> None:
    rows = group_rows([line("Total", 100), line("172.50", 104, x=400), line("Date", 160)])
    assert [[ln.text for ln in row] for row in rows] == [["Total", "172.50"], ["Date"]]


def test_arabic_row_is_read_right_to_left() -> None:
    row = group_rows([line("أحمد", 10, x=40), line("عمر", 10, x=300)])[0]
    assert join_row(row) == "عمر أحمد"


def test_mixed_row_is_read_left_to_right() -> None:
    row = group_rows([line("Patient", 10, x=40), line("عمر", 10, x=300)])[0]
    assert join_row(row) == "Patient عمر"
