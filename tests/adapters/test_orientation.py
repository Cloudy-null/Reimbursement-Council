"""Photos the right way up: EXIF on upload, and trying turns when a reading is weak."""

import io
import json
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from reimbursement_council.adapters.orientation import rotated, upright_upload
from reimbursement_council.adapters.vision_reader import VisionReader
from reimbursement_council.core.models.claim import Document
from reimbursement_council.core.receipt_rows import OcrLine
from tests.adapters.test_vision_reader import GOOD, ROWS, FakeModel, settings


def size_of(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size


def test_exif_orientation_is_applied_on_upload() -> None:
    image = Image.new("RGB", (80, 40), "white")
    exif = image.getexif()
    exif[0x0112] = 6  # the camera was turned: show it turned 90 degrees
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    assert size_of(upright_upload(out.getvalue(), ".jpg")) == (40, 80)


def test_a_photo_without_exif_is_left_alone() -> None:
    out = io.BytesIO()
    Image.new("RGB", (80, 40), "white").save(out, format="PNG")
    assert upright_upload(out.getvalue(), ".png") == out.getvalue()
    assert size_of(rotated(out.getvalue(), 90)) == (40, 80)


class UprightOnlyEngine:
    """Reads text only when the page stands upright (taller than wide)."""

    name = "upright-only"

    def read(self, image_bytes: bytes) -> list[OcrLine]:
        width, height = size_of(image_bytes)
        if width > height:
            return []
        return [
            OcrLine(text=text, confidence=0.95, box=(10, 40 * i, 300, 40 * i + 30))
            for i, text in enumerate(ROWS)
        ]


def test_a_sideways_photo_is_read_after_turning_it(tmp_path: Path) -> None:
    path = tmp_path / "sideways.png"
    Image.new("RGB", (120, 60), "white").save(path)  # wider than tall: on its side
    document = Document(
        document_id="d1",
        claim_id="c1",
        kind="receipt",
        file_path=str(path),
        image_hash=None,
        uploaded_at=datetime(2026, 11, 25, tzinfo=UTC),
    )
    model = FakeModel(*[json.dumps(GOOD)] * 4)
    output = VisionReader(model, UprightOnlyEngine(), settings(tmp_path, rotation=True)).read(
        document
    )
    assert output.reader_counts["rotated_degrees"] in (90, 270)
    assert {f.name for f in output.fields} >= {"total", "treatment_date"}
