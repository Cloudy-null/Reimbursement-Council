"""Readers turn one document file into a ReaderOutput.

FixtureReader reads a hand-written *.reading.json (tests and demo). QrImageReader reads QR codes
from an image; text reading (EasyOCR) comes in the next plan.
"""

import json
import logging
from pathlib import Path
from typing import Protocol

from reimbursement_council.adapters.qr_image import find_qr_payloads
from reimbursement_council.core.models.claim import Document, ReaderOutput

logger = logging.getLogger(__name__)

FIXTURE_SUFFIX = ".reading.json"
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})


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


class QrImageReader:
    """Reads only the QR codes of an image for now."""

    def read(self, document: Document) -> ReaderOutput:
        payloads = find_qr_payloads(Path(document.file_path).read_bytes())
        logger.info("document %s: %d QR codes found", document.document_id, len(payloads))
        return ReaderOutput(fields=[], line_items=[], qr_payloads=payloads)


def reader_for(document: Document) -> DocumentReader:
    """Pick a reader by file type."""
    name = Path(document.file_path).name.lower()
    if name.endswith(FIXTURE_SUFFIX):
        return FixtureReader()
    suffix = Path(name).suffix
    if suffix in IMAGE_SUFFIXES:
        return QrImageReader()
    raise ValueError(f"no reader for file type {suffix or name!r}")
