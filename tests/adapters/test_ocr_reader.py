import hashlib
import importlib.util
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from reimbursement_council.adapters import ocr_engine
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
from reimbursement_council.core.receipt_rows import OcrLine, group_rows, join_row
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


def test_fresh_easyocr_uses_the_cache_without_loading_the_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A new run starts with the model not loaded. The cache name must already be right then,
    # or the first image of every run is read again.
    monkeypatch.setattr(ocr_engine, "package_version", lambda name: "9.9.9", raising=False)
    monkeypatch.setitem(sys.modules, "easyocr", None)  # loading the model would fail
    image = b"image bytes"
    cache = tmp_path / "cache"
    cache.mkdir()
    digest = hashlib.sha256(image).hexdigest()
    line = {"text": "Total", "confidence": 0.9, "box": [0, 0, 10, 10]}
    (cache / f"{digest}-easyocr-9.9.9-ar-en.json").write_text(json.dumps([line]), "utf-8")
    lines = CachedOcrEngine(EasyOcrEngine(), cache).read(image)
    assert [x.text for x in lines] == ["Total"]


def test_half_written_cache_file_is_read_again(tmp_path: Path) -> None:
    # A run killed while writing leaves a cut off file. The next run must not crash on it.
    engine = FakeEngine(load("pharmacy_bilingual"))
    cache = tmp_path / "cache"
    CachedOcrEngine(engine, cache).read(b"image bytes")
    path = next(cache.glob("*.json"))
    path.write_text('[{"text": "To', encoding="utf-8")
    lines = CachedOcrEngine(engine, cache).read(b"image bytes")
    assert engine.calls == 2 and lines == engine.lines
    assert len(json.loads(path.read_text(encoding="utf-8"))) == len(engine.lines)


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


def test_ocr_reader_keeps_the_text_row_by_row(tmp_path: Path) -> None:
    path, _ = drawn_png(tmp_path)
    lines = load("clinic_bilingual")
    settings = repo_settings()
    output = QrOcrReader(FakeEngine(lines), settings).read(document(path))
    rows = group_rows(lines, settings.decision.ocr.row_overlap)
    assert output.text_lines == [join_row(row) for row in rows]
    assert any("Al Noor" in line for line in output.text_lines)
