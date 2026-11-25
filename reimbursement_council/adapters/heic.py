"""iPhone photos come as HEIC. We turn them into JPEG on upload, so every reader can open them.

Uses pillow-heif (decision 013). A file that is not a real HEIC image is refused as a wrong type.
"""

import io

from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()

HEIC_SUFFIXES = frozenset({".heic", ".heif"})
JPEG_QUALITY = 92


def heic_to_jpeg(data: bytes) -> bytes:
    """The photo as JPEG bytes. Raises ValueError when the bytes are not a HEIC image."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            out = io.BytesIO()
            image.convert("RGB").save(out, format="JPEG", quality=JPEG_QUALITY)
            return out.getvalue()
    except (OSError, ValueError, SyntaxError) as error:
        raise ValueError(f"not a HEIC image: {error}") from error
