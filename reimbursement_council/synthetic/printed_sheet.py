"""A document as a list of printed rows: what a page says, in order. Pure: no drawing.

The optical, dental, payment and language documents are built as sheets. The drawing adapter
(adapters/sheet_drawing.py) turns a sheet into an image, and tests read the rows, not the image.
"""

from typing import Literal

from pydantic import Field

from reimbursement_council.core.models.common import Model

RowStyle = Literal["title", "heading", "center", "pair", "table", "table_head", "rule", "small"]
Direction = Literal["rtl", "ltr"]
PageShape = Literal["a4", "slip"]


class SheetRow(Model):
    style: RowStyle
    cells: list[str] = Field(default_factory=list)
    # The truth field this row prints (its box is recorded), for example "total".
    field: str | None = None
    # A row printed in the other direction, for example a left to right eye table on an
    # Arabic invoice. None: the sheet's direction.
    direction: Direction | None = None


class Sheet(Model):
    rows: list[SheetRow]
    direction: Direction = "rtl"
    page: PageShape = "a4"

    def text(self) -> str:
        """Everything the page says, one row per line, in reading order."""
        return "\n".join(" ".join(row.cells) for row in self.rows if row.cells)


def title(text: str, field: str | None = None) -> SheetRow:
    return SheetRow(style="title", cells=[text], field=field)


def heading(text: str) -> SheetRow:
    return SheetRow(style="heading", cells=[text])


def center(text: str, field: str | None = None) -> SheetRow:
    return SheetRow(style="center", cells=[text], field=field)


def pair(label: str, value: str, field: str | None = None) -> SheetRow:
    return SheetRow(style="pair", cells=[label, value], field=field)


def table_head(*cells: str, direction: Direction | None = None) -> SheetRow:
    return SheetRow(style="table_head", cells=list(cells), direction=direction)


def table_row(
    *cells: str, field: str | None = None, direction: Direction | None = None
) -> SheetRow:
    return SheetRow(style="table", cells=list(cells), field=field, direction=direction)


def rule() -> SheetRow:
    return SheetRow(style="rule")


def small(text: str) -> SheetRow:
    return SheetRow(style="small", cells=[text])
