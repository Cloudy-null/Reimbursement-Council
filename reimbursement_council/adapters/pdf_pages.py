"""Turn a PDF (a digital invoice or a scan) into one PNG image, so the image reader can read it.

Pages are drawn with pdfium (pypdfium2, decision 009) and stacked top to bottom, up to
max_pages. Nothing leaves the computer.
"""

import io

import pypdfium2 as pdfium
from PIL import Image


def pdf_as_image(data: bytes, max_pages: int, scale: float) -> bytes:
    """The first max_pages pages, one under the other, as PNG bytes. A file that is not a
    readable PDF raises ValueError."""
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as error:
        raise ValueError(f"not a readable PDF: {error}") from error
    try:
        count = min(len(pdf), max_pages)
        if count == 0:
            raise ValueError("the PDF has no pages")
        pages = [pdf[i].render(scale=scale).to_pil().convert("RGB") for i in range(count)]
    finally:
        pdf.close()
    width = max(page.width for page in pages)
    sheet = Image.new("RGB", (width, sum(page.height for page in pages)), "white")
    top = 0
    for page in pages:
        sheet.paste(page, (0, top))
        top += page.height
    buffer = io.BytesIO()
    sheet.save(buffer, format="PNG")
    return buffer.getvalue()
