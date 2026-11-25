"""Code review, untrusted uploads: a bad file is a ValueError (refused or read as empty, never a
500), PDFs are drawn one at a time, and a PDF cannot ask for a huge image."""

import io
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image

from reimbursement_council.adapters import pdf_pages
from reimbursement_council.adapters.pdf_pages import pdf_as_image
from reimbursement_council.adapters.readers import QrOcrReader
from reimbursement_council.core.models.claim import Document
from reimbursement_council.core.receipt_rows import OcrLine
from tests.factories import repo_settings


class BrokenEngine:
    """Like EasyOCR on a file it cannot decode: raises an error that is not a ValueError."""

    name = "broken"

    def read(self, image_bytes: bytes) -> list[OcrLine]:
        raise RuntimeError("cv2.error: (-215) !_src.empty() in reformat_input")


def document(path: Path) -> Document:
    return Document(
        document_id="d",
        claim_id="c",
        kind="other",
        file_path=str(path),
        image_hash=None,
        uploaded_at=datetime(2026, 11, 25, tzinfo=UTC),
    )


def test_an_ocr_error_on_a_bad_file_becomes_a_value_error(tmp_path: Path) -> None:
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"not really a jpeg")
    with pytest.raises(ValueError, match="could not be read"):
        QrOcrReader(BrokenEngine(), repo_settings()).read(document(path))  # type: ignore[arg-type]


def big_page_pdf(points: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buffer, format="PDF", resolution=72)
    data = buffer.getvalue()
    return data.replace(
        b"/MediaBox [ 0 0 100 100 ]", f"/MediaBox [ 0 0 {points} {points} ]".encode()
    )


def test_a_huge_pdf_page_is_drawn_smaller_to_stay_under_the_pixel_limit() -> None:
    limit = 4_000_000
    png = pdf_as_image(big_page_pdf(14_400), max_pages=3, scale=2.0, max_pixels=limit)
    image = Image.open(io.BytesIO(png))
    assert image.width * image.height <= limit * 1.01


def test_pdfs_are_drawn_one_at_a_time(monkeypatch: pytest.MonkeyPatch) -> None:
    inside = 0
    most = 0
    real = pdf_pages._render_pages

    def counting(*args: object) -> object:
        nonlocal inside, most
        inside += 1
        most = max(most, inside)
        try:
            return real(*args)  # type: ignore[arg-type]
        finally:
            inside -= 1

    monkeypatch.setattr(pdf_pages, "_render_pages", counting)
    pdf = big_page_pdf(300)
    threads = [threading.Thread(target=pdf_as_image, args=(pdf, 1, 1.0, 10**7)) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert most == 1
