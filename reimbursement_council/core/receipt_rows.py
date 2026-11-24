"""Group OCR text boxes into rows and read each row in order. Pure logic, no OCR here.

A row is a set of boxes whose vertical centers are close. Boxes in a row are sorted left to
right, and a row of only Arabic boxes is read right to left.
"""

import re
from statistics import mean

from reimbursement_council.core.models.common import Model, Score

Box = tuple[int, int, int, int]

ARABIC_LETTERS = re.compile("[؀-ۿ]")
LATIN_LETTERS = re.compile("[A-Za-z]")


class OcrLine(Model):
    """One text box from the OCR engine. box is x0, y0, x1, y1 in pixels."""

    text: str
    confidence: Score
    box: Box


def _center(line: OcrLine) -> float:
    return (line.box[1] + line.box[3]) / 2


def _height(line: OcrLine) -> int:
    return max(1, line.box[3] - line.box[1])


def group_rows(lines: list[OcrLine], overlap: float = 0.5) -> list[list[OcrLine]]:
    """Lines whose vertical centers are close form one row, sorted left to right."""
    rows: list[list[OcrLine]] = []
    for item in sorted(lines, key=_center):
        if rows:
            row = rows[-1]
            row_center = mean(_center(x) for x in row)
            limit = overlap * min(_height(item), min(_height(x) for x in row))
            if abs(_center(item) - row_center) <= limit:
                row.append(item)
                continue
        rows.append([item])
    return [sorted(row, key=lambda x: x.box[0]) for row in rows]


def _is_arabic(text: str) -> bool:
    return bool(ARABIC_LETTERS.search(text)) and not LATIN_LETTERS.search(text)


def join_row(lines: list[OcrLine]) -> str:
    """Join text boxes in reading order: right to left when they are Arabic."""
    if lines and all(_is_arabic(x.text) for x in lines):
        lines = sorted(lines, key=lambda x: -x.box[0])
    return " ".join(x.text.strip() for x in lines)
