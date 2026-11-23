import random

import cv2
import numpy as np
import pytest

from reimbursement_council.adapters.qr_image import find_qr_payloads
from reimbursement_council.adapters.receipt_drawing import Damage, draw_receipt, shape_text
from reimbursement_council.synthetic.receipt_content import (
    LAYOUTS,
    PROVIDERS,
    Layout,
    ReceiptContent,
    ReceiptOptions,
    make_receipt_content,
)
from tests.factories import repo_settings


def content(seed: int = 3, **options: object) -> ReceiptContent:
    s = repo_settings()
    return make_receipt_content(
        random.Random(seed), s.prices, ReceiptOptions(**options), s.policy.vat_rate
    )


def decode(png: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    return image


def test_png_decodes_and_qr_reads_back() -> None:
    receipt = content(3)
    drawn = draw_receipt(receipt)
    image = decode(drawn.png)
    assert image.shape[1] == drawn.width and image.shape[0] == drawn.height
    assert find_qr_payloads(drawn.png) == [receipt.qr_payload]


def test_receipt_without_qr_has_none() -> None:
    assert find_qr_payloads(draw_receipt(content(4, with_qr=False)).png) == []


def test_arabic_is_shaped_for_drawing() -> None:
    shaped = shape_text("عيادة النور")
    assert any("ﹰ" <= char <= "﻿" for char in shaped)  # joined letter forms
    assert shape_text("Total SAR") == "Total SAR"


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_layout_draws_with_boxes_inside(layout: Layout) -> None:
    provider = PROVIDERS[2] if layout == "pharmacy_bilingual" else PROVIDERS[0]
    drawn = draw_receipt(content(5, layout=layout, provider=provider, unlisted_item=True))
    decode(drawn.png)
    assert {"total", "subtotal", "vat_total", "vat_number"} <= set(drawn.boxes)
    for boxes in drawn.boxes.values():
        for x0, y0, x1, y1 in boxes:
            assert 0 <= x0 < x1 <= drawn.width and 0 <= y0 < y1 <= drawn.height


def test_damage_changes_pixels_but_still_decodes() -> None:
    receipt = content(6)
    clean = draw_receipt(receipt)
    damaged = draw_receipt(
        receipt, Damage(blur_sigma=1.2, rotate_degrees=2.0, noise_std=8.0, jpeg_quality=60, seed=1)
    )
    assert damaged.png != clean.png
    decode(damaged.png)
