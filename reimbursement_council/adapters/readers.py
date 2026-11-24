"""Readers turn one document file into a ReaderOutput.

FixtureReader reads a hand-written *.reading.json (tests and demo). QrImageReader reads only the
QR codes of an image. QrOcrReader reads the QR codes and the printed text (OCR plus parsing).
"""

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from reimbursement_council.adapters.ocr_engine import OcrEngine
from reimbursement_council.adapters.pdf_pages import pdf_as_image
from reimbursement_council.adapters.qr_image import find_qr_payloads
from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import Document, ReaderOutput
from reimbursement_council.core.receipt_parsing import parse_receipt_lines
from reimbursement_council.core.receipt_rows import group_rows, join_row

logger = logging.getLogger(__name__)

FIXTURE_SUFFIX = ".reading.json"
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})
PDF_SUFFIX = ".pdf"


class DocumentReader(Protocol):
    def read(self, document: Document) -> ReaderOutput: ...


class FixtureReader:
    """Loads a reading file. Fields get the document's id, so the file does not repeat it."""

    def read(self, document: Document) -> ReaderOutput:
        data = json.loads(Path(document.file_path).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for field in data.get("fields", []):
                if isinstance(field, dict):
                    field["document_id"] = document.document_id
        output = ReaderOutput.model_validate(data)
        logger.info(
            "fixture reading for document %s: %d fields, %d items",
            document.document_id,
            len(output.fields),
            len(output.line_items),
        )
        return output


def document_image(document: Document, settings: Settings | None) -> bytes:
    """The document as image bytes: a photo as it is, a PDF drawn as one image."""
    data = Path(document.file_path).read_bytes()
    if Path(document.file_path).suffix.lower() != PDF_SUFFIX:
        return data
    if settings is None:
        raise ValueError("reading a PDF needs the settings (max pages and zoom)")
    return pdf_as_image(data, settings.documents.max_pdf_pages, settings.documents.pdf_render_scale)


class QrImageReader:
    """Reads only the QR codes of an image or PDF."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings

    def read(self, document: Document) -> ReaderOutput:
        payloads = find_qr_payloads(document_image(document, self._settings))
        logger.info("document %s: %d QR codes found", document.document_id, len(payloads))
        return ReaderOutput(fields=[], line_items=[], qr_payloads=payloads)


class QrOcrReader:
    """QR codes plus the printed text, read with an OCR engine and parsed into fields."""

    def __init__(self, engine: OcrEngine, settings: Settings) -> None:
        self._engine = engine
        self._settings = settings

    def read(self, document: Document) -> ReaderOutput:
        image = document_image(document, self._settings)
        payloads = find_qr_payloads(image)
        lines = self._engine.read(image)
        parsed = parse_receipt_lines(document.document_id, lines, self._settings)
        logger.info(
            "document %s: %d QR codes, %d text boxes, %d fields, %d items",
            document.document_id,
            len(payloads),
            len(lines),
            len(parsed.fields),
            len(parsed.line_items),
        )
        rows = group_rows(lines, self._settings.decision.ocr.row_overlap)
        text_lines = [join_row(row) for row in rows]
        return parsed.model_copy(update={"qr_payloads": payloads, "text_lines": text_lines})


def make_reader_for(settings: Settings, engine: OcrEngine) -> Callable[[Document], DocumentReader]:
    """Reader picker for the configured image reader (easyocr or qr_only)."""

    def pick(document: Document) -> DocumentReader:
        reader = reader_for(document)
        if isinstance(reader, QrImageReader):
            if settings.decision.reader == "easyocr":
                return QrOcrReader(engine, settings)
            return QrImageReader(settings)
        return reader

    return pick


def reader_for(document: Document) -> DocumentReader:
    """Pick a reader by file type."""
    name = Path(document.file_path).name.lower()
    if name.endswith(FIXTURE_SUFFIX):
        return FixtureReader()
    suffix = Path(name).suffix
    if suffix in IMAGE_SUFFIXES or suffix == PDF_SUFFIX:
        return QrImageReader()
    raise ValueError(f"no reader for file type {suffix or name!r}")
