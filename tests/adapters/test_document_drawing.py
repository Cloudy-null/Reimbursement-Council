"""Task 9: prescriptions and medical reports drawn like the receipts, with true values."""

import importlib.util
import random
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import pytest

from reimbursement_council.adapters.document_drawing import draw_clinical_document
from reimbursement_council.adapters.receipt_drawing import DAMAGE_PRESETS, draw_receipt
from reimbursement_council.core.document_kinds import detect_kind
from reimbursement_council.core.models.claim import Document
from reimbursement_council.synthetic.document_content import (
    HEADERS,
    ClinicalDocument,
    make_clinical_document,
)
from reimbursement_council.synthetic.receipt_content import PATIENTS, PROVIDERS
from tests.adapters.test_receipt_drawing import content
from tests.factories import repo_settings


def clinical(kind: str = "prescription", seed: int = 4) -> ClinicalDocument:
    s = repo_settings()
    services = (
        [s.prices["MED-PARA"], s.prices["MED-IBU"]]
        if kind == "prescription"
        else [s.prices["CONS-GP"]]
    )
    return make_clinical_document(
        random.Random(seed),
        kind,
        PROVIDERS[0],
        PATIENTS[0],  # type: ignore[arg-type]
        datetime(2026, 11, 15, 10, 30),
        services,
    )


def test_receipt_drawing_is_the_same_every_time_after_the_move() -> None:
    # The move to drawing_canvas.py was checked byte for byte on Windows at f6f888b. A fixed
    # hash is not used here: font rendering differs between platforms, so CI on Linux draws
    # other bytes.
    assert draw_receipt(content(20)).png == draw_receipt(content(20)).png
    damaged = draw_receipt(content(21), DAMAGE_PRESETS["light"]).png
    assert damaged == draw_receipt(content(21), DAMAGE_PRESETS["light"]).png
    assert damaged != draw_receipt(content(21)).png


def test_prescription_lists_the_medicines_and_the_patient() -> None:
    document = clinical("prescription")
    assert document.kind == "prescription" and document.patient == PATIENTS[0]
    assert any("Paracetamol" in line for line in document.lines)
    assert clinical("prescription") == clinical("prescription")  # same seed, same document


def test_prescription_draws_patient_date_and_provider_boxes() -> None:
    drawn = draw_clinical_document(clinical("prescription"))
    image = cv2.imdecode(np.frombuffer(drawn.png, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None and image.shape[1] == drawn.width
    assert {"patient_name", "treatment_date", "provider_name"} <= set(drawn.boxes)
    for boxes in drawn.boxes.values():
        for x0, y0, x1, y1 in boxes:
            assert 0 <= x0 < x1 <= drawn.width and 0 <= y0 < y1 <= drawn.height


@pytest.mark.parametrize("kind", ["prescription", "medical_report"])
def test_report_header_has_both_language_keywords(kind: str) -> None:
    english, arabic = HEADERS[kind]  # type: ignore[index]
    config = repo_settings().documents
    assert detect_kind([english], [], config) == kind
    assert detect_kind([arabic], [], config) == kind


def test_damage_applies_to_clinical_documents() -> None:
    document = clinical("medical_report")
    assert (
        draw_clinical_document(document).png
        != draw_clinical_document(document, DAMAGE_PRESETS["light"]).png
    )


@pytest.mark.slow
@pytest.mark.skipif(importlib.util.find_spec("easyocr") is None, reason="needs the ocr extra")
def test_easyocr_reads_a_drawn_prescription_as_a_prescription_for_the_right_patient(
    tmp_path: Path,
) -> None:
    from reimbursement_council.adapters.ocr_engine import EasyOcrEngine
    from reimbursement_council.adapters.readers import QrOcrReader

    path = tmp_path / "rx.png"
    path.write_bytes(draw_clinical_document(clinical("prescription")).png)
    document = Document(
        document_id="rx",
        claim_id="c",
        kind="other",
        file_path=str(path),
        image_hash=None,
        uploaded_at=datetime(2026, 11, 20, tzinfo=UTC),
    )
    s = repo_settings()
    reading = QrOcrReader(EasyOcrEngine(), s).read(document)
    assert detect_kind(reading.text_lines, reading.qr_payloads, s.documents) == "prescription"
    names = [f.value for f in reading.fields if f.name == "patient_name"]
    assert names and names[0].casefold() == PATIENTS[0].en.casefold()
