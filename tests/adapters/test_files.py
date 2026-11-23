import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from reimbursement_council.adapters.files import load_claim_file, load_reference_file

CLAIM = {
    "claim_id": "claim-a",
    "member_id": "m1",
    "patient_member_id": "m1",
    "policy_id": "p1",
    "submitted_at": "2026-11-20T09:00:00Z",
    "status": "submitted",
    "retries_used": 0,
    "documents": [
        {
            "document_id": "doc-1",
            "claim_id": "claim-a",
            "kind": "receipt",
            "file_path": "clean.reading.json",
            "image_hash": "trust-me",
            "uploaded_at": "2026-11-20T09:00:00Z",
        }
    ],
}


def write_claim(folder: Path, claim: dict[str, object] = CLAIM) -> Path:
    path = folder / "clean.claim.json"
    path.write_text(json.dumps(claim), encoding="utf-8")
    return path


def test_load_claim_resolves_and_hashes(tmp_path: Path) -> None:
    (tmp_path / "clean.reading.json").write_bytes(b'{"fields": []}')
    claim = load_claim_file(write_claim(tmp_path))
    document = claim.documents[0]
    assert Path(document.file_path) == (tmp_path / "clean.reading.json").resolve()
    assert document.image_hash == hashlib.sha256(b'{"fields": []}').hexdigest()


def test_load_claim_missing_document_names_it(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"clean\.reading\.json"):
        load_claim_file(write_claim(tmp_path))


def test_load_claim_bad_shape_raises_validation_error(tmp_path: Path) -> None:
    (tmp_path / "clean.reading.json").write_text("{}", encoding="utf-8")
    bad = dict(CLAIM)
    bad["submitted_at"] = "2026-11-20T09:00:00"  # no timezone
    with pytest.raises(ValidationError):
        load_claim_file(write_claim(tmp_path, bad))


def test_load_claim_not_json_raises_value_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.claim.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match=r"broken\.claim\.json"):
        load_claim_file(path)


def test_load_reference(tmp_path: Path) -> None:
    path = tmp_path / "reference.json"
    path.write_text(
        json.dumps({"members": [], "policies": [], "providers": [], "histories": []}),
        encoding="utf-8",
    )
    assert load_reference_file(path).members == []
