"""Load claim and reference files from disk. Everything is validated; nothing in them is trusted.

Document paths are resolved against the claim file's folder, and the image hash is always
computed from the file bytes, never taken from the file.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from reimbursement_council.core.models.claim import Claim
from reimbursement_council.core.models.reference import ReferenceData


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{path.name} is not valid JSON: {error}") from error


def load_claim_file(path: Path) -> Claim:
    data = _read_json(path)
    if isinstance(data, dict):
        for document in data.get("documents", []):
            if not isinstance(document, dict) or not isinstance(document.get("file_path"), str):
                continue
            document_path = (path.parent / document["file_path"]).resolve()
            if not document_path.is_file():
                raise FileNotFoundError(f"document file not found: {document_path}")
            document["file_path"] = str(document_path)
            document["image_hash"] = hashlib.sha256(document_path.read_bytes()).hexdigest()
    return Claim.model_validate(data)


def load_reference_file(path: Path) -> ReferenceData:
    return ReferenceData.model_validate(_read_json(path))
