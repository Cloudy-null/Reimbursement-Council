"""Draw a Sheet (synthetic/printed_sheet.py) as a PNG on the shared canvas.

Right to left sheets put labels on the right and values to their left, like a printed Arabic
invoice. Tables spread their cells over fixed columns. An A4 sheet is padded to a portrait
page. Boxes are recorded for every row that names a truth field.
"""

import io
import re

from reimbursement_council.adapters.drawing_canvas import (
    MARGIN,
    RIGHT,
    WIDTH,
    Canvas,
    Damage,
    DrawnReceipt,
    damage_image,
    font,
    shape_text,
)
from reimbursement_council.synthetic.printed_sheet import Sheet, SheetRow

A4_HEIGHT = round(WIDTH * 297 / 210)  # portrait A4 shape at the canvas width
GAP = 16  # space between a label and its value
SIZES = {"title": 32, "heading": 26, "center": 20, "pair": 22, "table": 20, "table_head": 18}
SMALL = 16
# Right edges of right to left table columns, by column count (rightmost column first).
RTL_COLUMNS: dict[int, tuple[int, ...]] = {
    5: (RIGHT, 540, 290, 200, 110),
    4: (RIGHT, 470, 300, 150),
    3: (RIGHT, 400, 160),
    2: (RIGHT, 300),
}
# Left edges of left to right table columns, by column count (first column first).
LTR_COLUMNS: dict[int, tuple[int, ...]] = {4: (MARGIN, 430, 530, 630)}
LTR_STEP = 130  # other left to right tables: one column every this many pixels
_ARABIC = re.compile("[؀-ۿ]")  # left to right tables: one column every this many pixels


_SWAP = str.maketrans("()", ")(")


def _mirrored(text: str) -> str:
    """The bidi step in shape_text leaves brackets unmirrored in Arabic lines, so the printed
    "(15.0%)" came out as ")15.0%(". Swapping them first prints them the right way round."""
    return text.translate(_SWAP) if _ARABIC.search(text) else text


def _width(text: str, size: int, bold: bool = False) -> float:
    return float(font(size, bold).getlength(shape_text(_mirrored(text))))


def _put(
    c: Canvas,
    x: float,
    text: str,
    size: int,
    *,
    align: str = "left",
    bold: bool = False,
    field: str | None = None,
) -> None:
    c.text(x, _mirrored(text), size, align=align, bold=bold, field=field)


def _pair(c: Canvas, row: SheetRow, rtl: bool) -> None:
    label, value = row.cells
    size = SIZES["pair"]
    if rtl:
        _put(c, RIGHT, label, size, align="right", bold=True)
        _put(
            c, RIGHT - _width(label, size, True) - GAP, value, size, align="right", field=row.field
        )
    else:
        _put(c, MARGIN, label, size, bold=True)
        _put(c, MARGIN + _width(label, size, True) + GAP, value, size, field=row.field)
    c.newline(size)


def _table(c: Canvas, row: SheetRow, rtl: bool) -> None:
    head = row.style == "table_head"
    size = SIZES[row.style]
    count = len(row.cells)
    for index, cell in enumerate(row.cells):
        if rtl:
            edges = RTL_COLUMNS.get(count) or tuple(
                RIGHT - i * (RIGHT - MARGIN) // count for i in range(count)
            )
            _put(c, edges[index], cell, size, align="right", bold=head, field=row.field)
        else:
            lefts = LTR_COLUMNS.get(count) or tuple(MARGIN + i * LTR_STEP for i in range(count))
            _put(c, lefts[index], cell, size, bold=head, field=row.field)
    c.newline(size)


def _wrapped(text: str, size: int) -> list[str]:
    """Words packed into lines that fit the page width."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and _width(candidate, size) > RIGHT - MARGIN:
            lines.append(current)
            current = word
        else:
            current = candidate
    return [*lines, current] if current else lines


def _row(c: Canvas, row: SheetRow, sheet_rtl: bool) -> None:
    rtl = sheet_rtl if row.direction is None else row.direction == "rtl"
    if row.style == "rule":
        c.rule()
    elif row.style in ("title", "heading", "center"):
        size = SIZES[row.style]
        bold = row.style != "center"
        _put(c, WIDTH / 2, row.cells[0], size, align="center", bold=bold, field=row.field)
        c.newline(size)
    elif row.style == "pair":
        _pair(c, row, rtl)
    elif row.style in ("table", "table_head"):
        _table(c, row, rtl)
    else:  # small print, wrapped
        for line in _wrapped(row.cells[0], SMALL):
            _put(c, RIGHT if rtl else MARGIN, line, SMALL, align="right" if rtl else "left")
            c.newline(SMALL)


def draw_sheet(sheet: Sheet, damage: Damage | None = None) -> DrawnReceipt:
    """The sheet as a PNG. The same sheet always gives the same image."""
    c = Canvas()
    rtl = sheet.direction == "rtl"
    for row in sheet.rows:
        _row(c, row, rtl)
    height = c.y + MARGIN
    if sheet.page == "a4":
        height = max(height, A4_HEIGHT)
    image = c.image.crop((0, 0, WIDTH, height))
    if damage is not None:
        image = damage_image(image, damage)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return DrawnReceipt(
        png=buffer.getvalue(), width=image.width, height=image.height, boxes=c.boxes
    )
