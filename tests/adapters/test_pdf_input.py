"""PDFs and scans: a PDF's pages are drawn into one image, so the same reader reads it."""

import io
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from reimbursement_council.adapters.pdf_pages import pdf_as_image
from reimbursement_council.adapters.qr_image import find_qr_payloads
from reimbursement_council.adapters.readers import QrImageReader, make_reader_for
from reimbursement_council.adapters.receipt_drawing import draw_receipt
from reimbursement_council.core.models.claim import Document
from tests.adapters.test_receipt_drawing import content
from tests.factories import repo_settings


def as_pdf(*pngs: bytes) -> bytes:
    pages = [Image.open(io.BytesIO(png)).convert("RGB") for png in pngs]
    buffer = io.BytesIO()
    pages[0].save(buffer, format="PDF", save_all=True, append_images=pages[1:], resolution=72)
    return buffer.getvalue()


def document(path: Path) -> Document:
    return Document(
        document_id="d1",
        claim_id="c",
        kind="other",
        file_path=str(path),
        image_hash=None,
        uploaded_at=datetime(2026, 11, 20, tzinfo=UTC),
    )


def height(png: bytes) -> int:
    image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    return int(image.shape[0])


def test_a_pdf_receipt_gives_the_same_qr_as_the_photo(tmp_path: Path) -> None:
    png = draw_receipt(content(5, with_qr=True)).png
    path = tmp_path / "receipt.pdf"
    path.write_bytes(as_pdf(png))
    reading = QrImageReader(repo_settings()).read(document(path))
    assert reading.qr_payloads == find_qr_payloads(png) != []


def test_pages_are_stacked_up_to_the_limit() -> None:
    png = draw_receipt(content(5)).png
    settings = repo_settings().documents
    one = height(
        pdf_as_image(as_pdf(png), settings.max_pdf_pages, settings.pdf_render_scale, 10**8)
    )
    many = as_pdf(*[png] * (settings.max_pdf_pages + 2))
    stacked = height(pdf_as_image(many, settings.max_pdf_pages, settings.pdf_render_scale, 10**8))
    assert stacked == one * settings.max_pdf_pages


def test_a_broken_pdf_is_a_value_error() -> None:
    with pytest.raises(ValueError, match="PDF"):
        pdf_as_image(b"%PDF-1.4 not really", 3, 2.0, 10**8)


def test_the_easyocr_picker_also_takes_pdfs(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    path.write_bytes(as_pdf(draw_receipt(content(5)).png))
    pick = make_reader_for(
        repo_settings().model_copy(
            update={"decision": repo_settings().decision.model_copy(update={"reader": "qr_only"})}
        ),
        engine=None,
    )  # type: ignore[arg-type]
    assert isinstance(pick(document(path)), QrImageReader)
