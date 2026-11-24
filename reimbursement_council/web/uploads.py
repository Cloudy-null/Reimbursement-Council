"""Uploaded files: refuse the bad ones one by one, save the good ones, read them once.

One bad file (wrong type, empty or too large) is refused with a message; the others are kept
(Review Focus 5). Each kept file is read right away and the reading is stored, so the check
screen and the decision see the same reading.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from reimbursement_council.core.models.claim import Document, ReaderOutput
from reimbursement_council.web.context import WebContext

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # a phone photo is a few MB; this only stops abuse


@dataclass(frozen=True)
class Upload:
    name: str
    data: bytes
    suffix: str


async def collect(files: list[UploadFile] | None) -> list[tuple[str, bytes]]:
    collected = []
    for file in files or []:
        if file.filename:
            collected.append((file.filename, await file.read()))
    return collected


def accept(files: list[tuple[str, bytes]]) -> tuple[list[Upload], list[str]]:
    """(kept uploads, refused file names with the reason)."""
    kept: list[Upload] = []
    refused: list[str] = []
    for name, data in files:
        suffix = Path(name).suffix.lower()
        if suffix not in IMAGE_SUFFIXES:
            refused.append(f"{name}: not a PNG or JPG photo")
        elif not data or len(data) > MAX_UPLOAD_BYTES:
            refused.append(f"{name}: empty or larger than 15 MB")
        else:
            kept.append(Upload(name=name, data=data, suffix=suffix))
    return kept, refused


def store_documents(
    ctx: WebContext, claim_id: str, uploads: list[Upload], first: int, now: datetime
) -> list[Document]:
    """Write each upload to disk and make its Document. The type is found when it is read."""
    ctx.uploads.mkdir(parents=True, exist_ok=True)
    documents = []
    for offset, upload in enumerate(uploads):
        path = ctx.uploads / f"{claim_id}-{first + offset}{upload.suffix}"
        path.write_bytes(upload.data)
        documents.append(
            Document(
                document_id=str(uuid4()),
                claim_id=claim_id,
                kind="other",
                file_path=str(path),
                image_hash=hashlib.sha256(upload.data).hexdigest(),
                uploaded_at=now,
            )
        )
    return documents


def read_and_store(ctx: WebContext, claim_id: str, documents: list[Document]) -> None:
    """Read each document once. A file the reader cannot handle gives an empty reading."""
    readings = {}
    for document in documents:
        try:
            reading = ctx.reader_for(document).read(document)
        except (ValueError, OSError) as error:
            logger.warning("claim %s: document could not be read: %s", claim_id, error)
            reading = ReaderOutput(fields=[], line_items=[], qr_payloads=[])
        readings[document.document_id] = reading
    ctx.store.save_readings(claim_id, readings)
