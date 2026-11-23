import cv2
import numpy as np

from reimbursement_council.adapters.qr_image import find_qr_payloads


def qr_png(text: str) -> bytes:
    img = cv2.QRCodeEncoder.create().encode(text)
    img = cv2.resize(img, None, fx=8, fy=8, interpolation=cv2.INTER_NEAREST)
    img = cv2.copyMakeBorder(img, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    return bytes(cv2.imencode(".png", img)[1].tobytes())


def test_reads_generated_qr() -> None:
    assert find_qr_payloads(qr_png("hello zatca")) == ["hello zatca"]


def test_blank_image_has_no_qr() -> None:
    white = np.full((200, 200, 3), 255, dtype=np.uint8)
    assert find_qr_payloads(bytes(cv2.imencode(".png", white)[1].tobytes())) == []


def test_not_an_image() -> None:
    assert find_qr_payloads(b"not an image") == []


def test_empty_bytes() -> None:
    assert find_qr_payloads(b"") == []
