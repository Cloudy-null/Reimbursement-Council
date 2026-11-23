import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from reimbursement_council.adapters.readers import FixtureReader, QrImageReader, reader_for
from reimbursement_council.core.models.claim import Document
from tests.adapters.test_qr_image import qr_png

READING = {
    "fields": [
        {
            "name": "total",
            "value": "17250",
            "original_text": "172.50",
            "source": "ocr",
            "confidence": 0.95,
        }
    ],
    "line_items": [
        {
            "description": "General consultation",
            "service_code": "CONS-GP",
            "quantity": 1,
            "unit_price": 15000,
            "amount": 15000,
            "confidence": 0.95,
        }
    ],
    "qr_payloads": ["payload"],
}


def document(path: Path) -> Document:
    return Document(
        document_id="doc-1",
        claim_id="claim-1",
        kind="receipt",
        file_path=str(path),
        image_hash=None,
        uploaded_at=datetime(2026, 11, 20, tzinfo=UTC),
    )


def test_fixture_reader_loads(tmp_path: Path) -> None:
    path = tmp_path / "clean.reading.json"
    path.write_text(json.dumps(READING), encoding="utf-8")
    output = FixtureReader().read(document(path))
    assert output.fields[0].value == "17250"
    assert output.fields[0].document_id == "doc-1"
    assert output.line_items[0].service_code == "CONS-GP"
    assert output.qr_payloads == ["payload"]


def test_fixture_reader_rejects_bad_confidence(tmp_path: Path) -> None:
    bad = json.loads(json.dumps(READING))
    bad["fields"][0]["confidence"] = 1.5
    path = tmp_path / "bad.reading.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValidationError):
        FixtureReader().read(document(path))


def test_qr_image_reader_reads_payload(tmp_path: Path) -> None:
    path = tmp_path / "receipt.png"
    path.write_bytes(qr_png("zatca payload"))
    output = QrImageReader().read(document(path))
    assert output.qr_payloads == ["zatca payload"]
    assert output.fields == [] and output.line_items == []


def test_reader_for_picks_by_suffix(tmp_path: Path) -> None:
    assert isinstance(reader_for(document(tmp_path / "a.reading.json")), FixtureReader)
    assert isinstance(reader_for(document(tmp_path / "a.PNG")), QrImageReader)
    assert isinstance(reader_for(document(tmp_path / "a.jpeg")), QrImageReader)
    with pytest.raises(ValueError, match=r"\.pdf"):
        reader_for(document(tmp_path / "a.pdf"))
