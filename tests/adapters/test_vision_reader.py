"""The local model reader with a fake model and a fake OCR engine (no GPU, no Ollama)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image

from reimbursement_council.adapters.local_model import LocalModelClient, LocalModelError
from reimbursement_council.adapters.vision_reader import VisionReader, smaller_image
from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import Document
from reimbursement_council.core.receipt_rows import OcrLine
from tests.factories import repo_settings

ROWS = ["Al Noor Clinic", "Date: 2026-11-17 10:55", "Total 345.00"]
GOOD = {
    "document_kind": "receipt",
    "provider_name": "Al Noor Clinic",
    "vat_number": None,
    "date": "17/11/2026",
    "time": "10:55",
    "patient_name": None,
    "subtotal": None,
    "vat_total": None,
    "total": "345.00",
    "items": [],
}


class FakeEngine:
    name = "fake"

    def read(self, image_bytes: bytes) -> list[OcrLine]:
        return [
            OcrLine(text=text, confidence=0.6, box=(10, 40 * i, 300, 40 * i + 30))
            for i, text in enumerate(ROWS)
        ]


class FakeModel:
    name = "fake-model"

    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.calls = 0

    def chat(
        self,
        prompt: str,
        images: list[bytes] | None = None,
        schema: object = None,
        system: str | None = None,
    ) -> str:  # noqa: E501
        self.calls += 1
        return self.answers.pop(0)


def settings(tmp_path: Path, two_readers: bool = True) -> Settings:
    base = repo_settings()
    local = base.local_model.model_copy(update={"cache_dir": str(tmp_path / "cache")})
    decision = base.decision.model_copy(
        update={"reader": "ollama", "two_readers_enabled": two_readers}
    )
    return base.model_copy(update={"local_model": local, "decision": decision})


def document(tmp_path: Path, color: str = "white") -> Document:
    path = tmp_path / f"{color}.png"
    Image.new("RGB", (60, 60), color).save(path)
    return Document(
        document_id="d1",
        claim_id="c1",
        kind="receipt",
        file_path=str(path),
        image_hash=None,
        uploaded_at=datetime(2026, 11, 25, tzinfo=UTC),
    )


def by_name(output: object) -> dict[str, tuple[str, float, str]]:
    return {f.name: (f.value, f.confidence, f.source) for f in output.fields}  # type: ignore[attr-defined]


def test_a_good_answer_gives_checked_fields_and_two_readers_agree(tmp_path: Path) -> None:
    s = settings(tmp_path)
    reader = VisionReader(FakeModel(json.dumps(GOOD)), FakeEngine(), s)
    output = reader.read(document(tmp_path))
    fields = by_name(output)
    assert fields["total"][0] == "34500" and fields["total"][2] == "vision"
    assert fields["treatment_date"][0] == "2026-11-17"
    # EasyOCR read the same date and total: confidence goes up to agree_confidence
    assert fields["total"][1] == s.decision.vision.agree_confidence
    assert output.kind_hint == "receipt"
    assert output.reader_counts["kept"] >= 3


def test_an_invalid_answer_is_asked_once_more(tmp_path: Path) -> None:
    model = FakeModel("not json", json.dumps(GOOD))
    output = VisionReader(model, FakeEngine(), settings(tmp_path)).read(document(tmp_path))
    assert model.calls == 2
    assert output.reader_counts["schema_failed"] == 1
    assert "total" in by_name(output)


def test_two_invalid_answers_fall_back_to_easyocr_only(tmp_path: Path) -> None:
    model = FakeModel("{}", "[]")
    output = VisionReader(model, FakeEngine(), settings(tmp_path)).read(document(tmp_path))
    assert model.calls == 2
    assert all(source == "ocr" for _, _, source in by_name(output).values())


def test_a_cached_answer_is_not_asked_again(tmp_path: Path) -> None:
    s = settings(tmp_path)
    first = FakeModel(json.dumps(GOOD))
    VisionReader(first, FakeEngine(), s).read(document(tmp_path))
    again = FakeModel()
    output = VisionReader(again, FakeEngine(), s).read(document(tmp_path))
    assert again.calls == 0 and "total" in by_name(output)


def test_a_made_up_total_is_dropped(tmp_path: Path) -> None:
    invented = GOOD | {"total": "99999.00"}
    output = VisionReader(
        FakeModel(json.dumps(invented)), FakeEngine(), settings(tmp_path, False)
    ).read(document(tmp_path))
    assert "total" not in by_name(output)
    assert output.reader_counts["made_up"] == 1


def test_a_model_error_keeps_the_easyocr_reading(tmp_path: Path) -> None:
    class Broken(FakeModel):
        def chat(self, *args: object, **kwargs: object) -> str:
            raise LocalModelError("down")

    output = VisionReader(Broken(), FakeEngine(), settings(tmp_path)).read(document(tmp_path))
    assert output.reader_counts["model_error"] == 1
    assert by_name(output)["total"][2] == "ocr"


def test_big_photos_are_scaled_down_for_the_model(tmp_path: Path) -> None:
    path = tmp_path / "big.png"
    Image.new("RGB", (4000, 3000), "white").save(path)
    small = smaller_image(path.read_bytes(), 1600)
    with Image.open(__import__("io").BytesIO(small)) as image:
        assert max(image.size) == 1600


@pytest.mark.slow
def test_the_real_model_gives_the_same_answer_twice() -> None:
    """Check 5, repeatability: temperature 0 and a fixed seed (needs Ollama; run with -m slow)."""
    image = sorted(Path("data/receipts/eval_s1").glob("*.png"))[0].read_bytes()
    from reimbursement_council.adapters.vision_reader import PROMPT, SYSTEM
    from reimbursement_council.core.vision_checks import ANSWER_SCHEMA

    client = LocalModelClient(repo_settings().local_model)
    first = client.chat(PROMPT, images=[image], schema=ANSWER_SCHEMA, system=SYSTEM)
    second = client.chat(PROMPT, images=[image], schema=ANSWER_SCHEMA, system=SYSTEM)
    assert json.loads(first) == json.loads(second)


def test_a_brand_name_item_gets_its_service_from_the_item_type_under_the_floor(
    tmp_path: Path,
) -> None:
    global ROWS
    saved = ROWS
    ROWS = [*saved, "1,600.00 1600 توكاى 1237"]
    try:
        brand = GOOD | {
            "items": [
                {
                    "description": "توکای",
                    "quantity": "1",
                    "amount": "1,600.00",
                    "item_type": "frame",
                }
            ]
        }
        s = settings(tmp_path)
        output = VisionReader(FakeModel(json.dumps(brand)), FakeEngine(), s).read(
            document(tmp_path)
        )
    finally:
        ROWS = saved
    assert [i.service_code for i in output.line_items] == ["OPT-FRAME"]
    assert output.line_items[0].confidence < s.decision.hard_rule_confidence_floor
