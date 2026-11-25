"""Turn a PDF (a digital invoice or a scan) into one PNG image, so the image reader can read it.

Pages are drawn with pdfium (pypdfium2, decision 009) and stacked top to bottom, up to
max_pages. Nothing leaves the computer.

A PDF is untrusted input (code review, day 4): pdfium is not thread-safe, so one PDF is drawn
at a time; a page that asks for a huge size is drawn smaller so it stays under max_pixels; and
any pdfium or image error becomes a ValueError, which the callers treat as an unread file.
"""

import io
import math
import threading

import pypdfium2 as pdfium
from PIL import Image

_PDFIUM = threading.Lock()


def _render_pages(data: bytes, max_pages: int, scale: float, max_pixels: int) -> list[Image.Image]:
    pdf = pdfium.PdfDocument(data)
    try:
        count = min(len(pdf), max_pages)
        if count == 0:
            raise ValueError("the PDF has no pages")
        pages = []
        for index in range(count):
            page = pdf[index]
            width, height = page.get_size()  # points
            page_scale = scale
            if width * height * scale * scale > max_pixels:
                page_scale = math.sqrt(max_pixels / (width * height))
            pages.append(page.render(scale=page_scale).to_pil().convert("RGB"))
        return pages
    finally:
        pdf.close()


def pdf_as_image(data: bytes, max_pages: int, scale: float, max_pixels: int) -> bytes:
    """The first max_pages pages, one under the other, as PNG bytes. A file that is not a
    readable PDF raises ValueError."""
    try:
        with _PDFIUM:
            pages = _render_pages(data, max_pages, scale, max_pixels)
    except (pdfium.PdfiumError, Image.DecompressionBombError, MemoryError) as error:
        raise ValueError(f"not a readable PDF: {error}") from error
    width = max(page.width for page in pages)
    sheet = Image.new("RGB", (width, sum(page.height for page in pages)), "white")
    top = 0
    for page in pages:
        sheet.paste(page, (0, top))
        top += page.height
    buffer = io.BytesIO()
    sheet.save(buffer, format="PNG")
    return buffer.getvalue()
