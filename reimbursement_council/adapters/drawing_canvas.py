"""The drawing canvas shared by receipts, prescriptions and medical reports.

Arabic is joined with arabic-reshaper and ordered with python-bidi before drawing, so the
image shows real Arabic. Fonts are bundled in assets/fonts so Windows and Linux draw the same.
Damage spoils a clean image like a quick phone photo.
"""

import re
from functools import cache
from pathlib import Path

import arabic_reshaper
import cv2
import numpy as np
from bidi import get_display
from PIL import Image, ImageDraw, ImageFont
from pydantic import Field

from reimbursement_council.core.models.common import Model

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
WIDTH = 760
MARGIN = 40
RIGHT = WIDTH - MARGIN
VALUE_X = 520  # right edge of values in label rows
INK, FAINT, RULE = (20, 20, 20), (105, 105, 105), (190, 190, 190)
_ARABIC = re.compile("[\u0600-\u06ff]")

Box = tuple[int, int, int, int]


class Damage(Model):
    """How much to spoil the clean image, like a quick phone photo."""

    blur_sigma: float = Field(default=0.0, ge=0)
    rotate_degrees: float = 0.0
    noise_std: float = Field(default=0.0, ge=0)
    jpeg_quality: int = Field(default=95, ge=10, le=100)
    seed: int = 0


DAMAGE_PRESETS: dict[str, Damage | None] = {
    "none": None,
    "unreadable": Damage(blur_sigma=3.0, rotate_degrees=4.0, noise_std=18.0, jpeg_quality=35),
    "light": Damage(blur_sigma=0.8, rotate_degrees=1.5, noise_std=4.0, jpeg_quality=80),
    "heavy": Damage(blur_sigma=1.4, rotate_degrees=3.0, noise_std=10.0, jpeg_quality=55),
}
"""How hard a generated receipt is spoiled, like a quick or careless phone photo."""


class DrawnReceipt(Model):
    png: bytes
    width: int
    height: int
    boxes: dict[str, list[Box]]


@cache
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "IBMPlexSansArabic-SemiBold.ttf" if bold else "IBMPlexSansArabic-Regular.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), size, layout_engine=ImageFont.Layout.BASIC)


def shape_text(text: str) -> str:
    """Arabic letters joined and put in visual order; other text unchanged."""
    if not _ARABIC.search(text):
        return text
    return str(get_display(arabic_reshaper.reshape(text)))


class Canvas:
    def __init__(self) -> None:
        self.image = Image.new("RGB", (WIDTH, 2400), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.y = MARGIN
        self.boxes: dict[str, list[Box]] = {}

    def text(
        self,
        x: float,
        text: str,
        size: int,
        *,
        align: str = "left",
        bold: bool = False,
        faint: bool = False,
        field: str | None = None,
    ) -> None:
        face = font(size, bold)
        shaped = shape_text(text)
        width = self.draw.textlength(shaped, font=face)
        start = x if align == "left" else x - width if align == "right" else x - width / 2
        self.draw.text((start, self.y), shaped, font=face, fill=FAINT if faint else INK)
        if field:
            x0, y0, x1, y1 = self.draw.textbbox((start, self.y), shaped, font=face)
            self.boxes.setdefault(field, []).append((int(x0), int(y0), int(x1) + 1, int(y1) + 1))

    def newline(self, size: int) -> None:
        self.y += int(size * 1.75)

    def rule(self) -> None:
        for x in range(MARGIN, RIGHT, 12):
            self.draw.line((x, self.y, x + 6, self.y), fill=RULE, width=1)
        self.y += 16

    def row(
        self,
        labels: tuple[str, str],
        value: str,
        field: str,
        size: int = 24,
        bold: bool = False,
        arabic_first: bool = False,
    ) -> None:
        english, arabic = labels
        arabic_size = size + 2 if arabic_first else size
        arabic_width = self.draw.textlength(shape_text(arabic), font=font(arabic_size, bold))
        value_right = min(VALUE_X, RIGHT - arabic_width - 24)  # never touch the Arabic label
        self.text(
            MARGIN, english, size - 4 if arabic_first else size, bold=bold and not arabic_first
        )
        self.text(value_right, value, size, align="right", bold=bold, field=field)
        self.text(RIGHT, arabic, arabic_size, align="right", bold=bold)
        self.newline(size)


def damage_image(image: Image.Image, damage: Damage) -> Image.Image:
    pixels = np.array(image)
    if damage.rotate_degrees:
        h, w = pixels.shape[:2]
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), damage.rotate_degrees, 1.0)
        pixels = cv2.warpAffine(pixels, matrix, (w, h), borderValue=(250, 250, 250))
    if damage.blur_sigma:
        pixels = cv2.GaussianBlur(pixels, (0, 0), damage.blur_sigma)
    if damage.noise_std:
        noise = np.random.default_rng(damage.seed).normal(0, damage.noise_std, pixels.shape)
        pixels = np.clip(pixels.astype(np.float64) + noise, 0, 255).astype(np.uint8)
    if damage.jpeg_quality < 95:
        ok, jpeg = cv2.imencode(".jpg", pixels, [cv2.IMWRITE_JPEG_QUALITY, damage.jpeg_quality])
        decoded = cv2.imdecode(jpeg, cv2.IMREAD_COLOR) if ok else None
        if decoded is not None:
            pixels = decoded
    return Image.fromarray(pixels)
