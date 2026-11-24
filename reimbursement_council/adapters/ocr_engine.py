"""OCR engines: EasyOCR (offline, Arabic and English) and a disk cache in front of any engine.

EasyOCR and PyTorch are an optional extra (uv sync --extra ocr), imported only when the first
image is read, so the app and the tests run without them.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Protocol

from reimbursement_council.core.receipt_rows import OcrLine

logger = logging.getLogger(__name__)

LANGUAGES = ["ar", "en"]


class OcrNotInstalledError(RuntimeError):
    """EasyOCR is not installed in this environment."""


class OcrEngine(Protocol):
    @property
    def name(self) -> str: ...

    def read(self, image_bytes: bytes) -> list[OcrLine]: ...


class EasyOcrEngine:
    """EasyOCR on the CPU. The model loads once, on the first read (about 15 to 30 seconds)."""

    def __init__(self) -> None:
        self._reader: Any = None
        self.name = "easyocr-ar-en"

    def _load(self) -> Any:
        if self._reader is None:
            try:
                import easyocr
            except ImportError as error:
                raise OcrNotInstalledError(
                    "EasyOCR is not installed. Run: uv sync --extra ocr"
                ) from error
            logger.info("loading EasyOCR models for %s", LANGUAGES)
            self._reader = easyocr.Reader(LANGUAGES, gpu=False, verbose=False)
            self.name = f"easyocr-{easyocr.__version__}-ar-en"
        return self._reader

    def read(self, image_bytes: bytes) -> list[OcrLine]:
        results = self._load().readtext(image_bytes)
        lines = []
        for box, text, confidence in results:
            xs = [int(point[0]) for point in box]
            ys = [int(point[1]) for point in box]
            lines.append(
                OcrLine(
                    text=str(text),
                    confidence=max(0.0, min(1.0, float(confidence))),
                    box=(min(xs), min(ys), max(xs), max(ys)),
                )
            )
        return lines


class CachedOcrEngine:
    """Reads each image once per engine; later reads come from JSON files on disk.

    The key is the image's sha256 plus the engine name, so a new engine version reads again.
    """

    def __init__(self, engine: OcrEngine, cache_dir: Path) -> None:
        self._engine = engine
        self._dir = cache_dir

    @property
    def name(self) -> str:
        return self._engine.name

    def read(self, image_bytes: bytes) -> list[OcrLine]:
        digest = hashlib.sha256(image_bytes).hexdigest()
        path = self._dir / f"{digest}-{self._engine.name}.json"
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            return [OcrLine.model_validate(item) for item in raw]
        lines = self._engine.read(image_bytes)
        self._dir.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([line.model_dump() for line in lines], ensure_ascii=False), encoding="utf-8"
        )
        return lines
