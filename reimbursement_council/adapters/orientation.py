"""Turning photos the right way up (core day 4b, a demo-critical fix).

- On upload: a phone photo carries an EXIF orientation flag; the pixels are turned to match it,
  so every reader sees the photo as the member saw it.
- When reading: a photo still on its side reads badly, so the reader may try it at 90, 180 and
  270 degrees and keep the strongest reading (adapters/vision_reader.py).
"""

import io

from PIL import Image, ImageOps

EXIF_ORIENTATION = 0x0112
JPEG_QUALITY = 92


def upright_upload(data: bytes, suffix: str) -> bytes:
    """The photo with its EXIF orientation applied, or the same bytes when there is none."""
    if suffix not in (".jpg", ".jpeg", ".png"):
        return data
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.getexif().get(EXIF_ORIENTATION, 1) == 1:
                return data
            turned = ImageOps.exif_transpose(image)
            out = io.BytesIO()
            if suffix == ".png":
                turned.save(out, format="PNG")
            else:
                turned.convert("RGB").save(out, format="JPEG", quality=JPEG_QUALITY)
            return out.getvalue()
    except (OSError, ValueError, SyntaxError):
        return data  # not an image we can open: the reader decides what to do with it


def rotated(data: bytes, degrees: int) -> bytes:
    """The image turned counterclockwise by degrees (90, 180 or 270), as PNG."""
    with Image.open(io.BytesIO(data)) as image:
        out = io.BytesIO()
        image.convert("RGB").rotate(degrees, expand=True).save(out, format="PNG")
        return out.getvalue()
