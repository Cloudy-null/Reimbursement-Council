"""Uploaded files: refuse the bad ones one by one, save the good ones, read them once.

One bad file (wrong type, empty or too large) is refused with a reason the page shows in its
language; the others are kept (Review Focus 5). Each file is named by its document id, so a
replaced or added file never overwrites another. Each kept file is read right away and the
reading is stored, so the check screen and the decision see the same reading.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from reimbursement_council.adapters.heic import HEIC_SUFFIXES, heic_to_jpeg
from reimbursement_council.core.models.claim import Document, ReaderOutput
from reimbursement_council.web.context import WebContext

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".pdf"})  # a PDF is drawn as an image


@dataclass(frozen=True)
class Refusal:
    name: str
    reason: str  # an i18n key: refused_type or refused_size


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


def accept(
    files: list[tuple[str, bytes]], max_megabytes: int, max_files: int
) -> tuple[list[Upload], list[Refusal]]:
    """(kept uploads, refused files with the reason). Only the first max_files are kept."""
    kept: list[Upload] = []
    refused: list[Refusal] = []
    for name, data in files:
        suffix = Path(name).suffix.lower()
        if len(kept) >= max_files:
            refused.append(Refusal(name, "refused_count"))
        elif suffix not in IMAGE_SUFFIXES and suffix not in HEIC_SUFFIXES:
            refused.append(Refusal(name, "refused_type"))
        elif not data or len(data) > max_megabytes * 1024 * 1024:
            refused.append(Refusal(name, "refused_size"))
        elif suffix in HEIC_SUFFIXES:  # an iPhone photo: turned into JPEG on upload
            try:
                kept.append(Upload(name=name, data=heic_to_jpeg(data), suffix=".jpg"))
            except ValueError:
                refused.append(Refusal(name, "refused_type"))
        else:
            kept.append(Upload(name=name, data=data, suffix=suffix))
    return kept, refused


def store_documents(
    ctx: WebContext, claim_id: str, uploads: list[Upload], now: datetime
) -> list[Document]:
    """Write each upload to disk and make its Document. The type is found when it is read."""
    ctx.uploads.mkdir(parents=True, exist_ok=True)
    documents = []
    for upload in uploads:
        document_id = str(uuid4())
        path = ctx.uploads / f"{claim_id}-{document_id}{upload.suffix}"
        path.write_bytes(upload.data)
        documents.append(
            Document(
                document_id=document_id,
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
