import importlib.util
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from reimbursement_council.adapters.ocr_engine import (
    CachedOcrEngine,
    EasyOcrEngine,
    OcrNotInstalledError,
)
from reimbursement_council.adapters.readers import (
    FixtureReader,
    QrImageReader,
    QrOcrReader,
    make_reader_for,
)
from reimbursement_council.adapters.receipt_drawing import draw_receipt
from reimbursement_council.core.models.claim import Document
from reimbursement_council.core.receipt_parsing import OcrLine
from reimbursement_council.synthetic.receipt_content import ReceiptOptions, make_receipt_content
from tests.core.test_receipt_parsing import load
from tests.factories import repo_settings, settings_with


class FakeEngine:
    name = "fake-1"

    def __init__(self, lines: list[OcrLine]) -> None:
        self.lines = lines
        self.calls = 0

    def read(self, image_bytes: bytes) -> list[OcrLine]:
        self.calls += 1
        return self.lines


def document(path: Path) -> Document:
    return Document(
        document_id="doc-1",
        claim_id="claim-1",
        kind="receipt",
        file_path=str(path),
        image_hash=None,
        uploaded_at=datetime(2026, 11, 20, tzinfo=UTC),
    )


def drawn_png(tmp_path: Path) -> tuple[Path, str]:
    s = repo_settings()
    content = make_receipt_content(random.Random(20), s.prices, ReceiptOptions(), s.policy.vat_rate)
    path = tmp_path / "receipt.png"
    path.write_bytes(draw_receipt(content).png)
    assert content.qr_payload is not None
    return path, content.qr_payload


def test_qr_ocr_reader_combines_qr_and_parsed_text(tmp_path: Path) -> None:
    path, payload = drawn_png(tmp_path)
    reader = QrOcrReader(FakeEngine(load("clinic_bilingual")), repo_settings())
    output = reader.read(document(path))
    assert output.qr_payloads == [payload]
    assert {f.name for f in output.fields} >= {"total", "subtotal", "vat_total", "vat_number"}
    assert all(f.document_id == "doc-1" for f in output.fields)
    assert len(output.line_items) == 4


def test_cache_reads_each_image_once(tmp_path: Path) -> None:
    engine = FakeEngine(load("pharmacy_bilingual"))
    cached = CachedOcrEngine(engine, tmp_path / "cache")
    first = cached.read(b"image bytes")
    second = CachedOcrEngine(engine, tmp_path / "cache").read(b"image bytes")
    assert first == second and engine.calls == 1
    assert len(list((tmp_path / "cache").glob("*.json"))) == 1
    cached.read(b"other image")
    assert engine.calls == 2


def test_missing_easyocr_says_how_to_install(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "easyocr", None)
    with pytest.raises(OcrNotInstalledError, match="uv sync --extra ocr"):
        EasyOcrEngine().read(b"x")


def test_reader_setting_picks_the_image_reader(tmp_path: Path) -> None:
    engine = FakeEngine([])
    png = document(tmp_path / "a.png")
    assert isinstance(make_reader_for(repo_settings(), engine)(png), QrOcrReader)
    qr_only = make_reader_for(settings_with(reader="qr_only"), engine)
    assert isinstance(qr_only(png), QrImageReader)
    assert isinstance(qr_only(document(tmp_path / "a.reading.json")), FixtureReader)


@pytest.mark.slow
@pytest.mark.skipif(importlib.util.find_spec("easyocr") is None, reason="needs the ocr extra")
def test_real_easyocr_reads_a_drawn_receipt(tmp_path: Path) -> None:
    s = repo_settings()
    content = make_receipt_content(random.Random(31), s.prices, ReceiptOptions(), s.policy.vat_rate)
    path = tmp_path / "r.png"
    path.write_bytes(draw_receipt(content).png)
    output = QrOcrReader(EasyOcrEngine(), s).read(document(path))
    totals = [f.value for f in output.fields if f.name == "total"]
    assert totals == [str(content.total)]
