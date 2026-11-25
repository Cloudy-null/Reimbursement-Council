"""HEIC photos (iPhone) are turned into JPEG on upload."""

import io

import pytest
from PIL import Image
from pillow_heif import register_heif_opener

from reimbursement_council.adapters.heic import heic_to_jpeg
from reimbursement_council.web.uploads import accept

register_heif_opener()


def heic_bytes() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (64, 48), "white").save(out, format="HEIF")
    return out.getvalue()


def test_a_heic_photo_becomes_a_jpeg() -> None:
    jpeg = heic_to_jpeg(heic_bytes())
    with Image.open(io.BytesIO(jpeg)) as image:
        assert image.format == "JPEG" and image.size == (64, 48)


def test_upload_accepts_heic_and_stores_it_as_jpeg() -> None:
    kept, refused = accept([("IMG_0001.HEIC", heic_bytes())], max_megabytes=15, max_files=10)
    assert refused == [] and [u.suffix for u in kept] == [".jpg"]
    assert kept[0].data[:3] == b"\xff\xd8\xff"


def test_a_fake_heic_is_refused_as_a_wrong_type() -> None:
    kept, refused = accept([("x.heic", b"not an image")], max_megabytes=15, max_files=10)
    assert kept == [] and [r.reason for r in refused] == ["refused_type"]


def test_not_heic_raises() -> None:
    with pytest.raises(ValueError):
        heic_to_jpeg(b"nope")
