"""Find QR codes in an image with OpenCV. Returns raw payloads; core decodes them."""

import logging

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def find_qr_payloads(image_bytes: bytes) -> list[str]:
    """Every non-empty QR payload in the image, in detection order. Never raises."""
    if not image_bytes:
        return []
    try:
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            logger.warning("bytes are not an image, no QR read")
            return []
        found, payloads, _points, _codes = cv2.QRCodeDetector().detectAndDecodeMulti(image)
    except cv2.error as error:
        logger.warning("OpenCV could not read the image: %s", error)
        return []
    if not found:
        return []
    return [str(payload) for payload in payloads if payload]
