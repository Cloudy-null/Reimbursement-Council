"""The damage suite: ten kinds of phone photo damage, each at levels 0 to 5.

Pure image functions: a PIL image in, a new PIL image of the same size out, nothing read or
written. Level 0 returns the image unchanged; levels 1 to 5 use the strengths in
config/synthetic.yaml (damage_suite). The same seed always gives the same damage, and the seed
does not depend on the level, so a glare spot or a fold stays in place and only grows.
"""

from collections.abc import Callable, Sequence

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

Pixels = NDArray[np.uint8]
PAPER = (250, 250, 250)  # what shows where the page moved away (a light table)

DAMAGE_KINDS: tuple[str, ...] = (
    "blur",
    "motion_blur",
    "noise",
    "jpeg",
    "low_resolution",
    "shadow",
    "glare",
    "perspective_tilt",
    "rotation",
    "crumpled_paper",
)
MAX_LEVEL = 5


def _blur(pixels: Pixels, strength: float, rng: np.random.Generator) -> Pixels:
    return np.asarray(cv2.GaussianBlur(pixels, (0, 0), strength), dtype=np.uint8)


def _motion_blur(pixels: Pixels, strength: float, rng: np.random.Generator) -> Pixels:
    length = max(3, int(strength) | 1)  # odd
    kernel = np.zeros((length, length), dtype=np.float32)
    kernel[length // 2, :] = 1.0
    angle = float(rng.uniform(-30, 30))  # the hand shakes mostly sideways
    turn = cv2.getRotationMatrix2D((length / 2 - 0.5, length / 2 - 0.5), angle, 1.0)
    turned = np.asarray(cv2.warpAffine(kernel, turn, (length, length)), dtype=np.float32)
    turned /= max(float(turned.sum()), 1e-6)
    return np.asarray(cv2.filter2D(pixels, -1, turned), dtype=np.uint8)


def _noise(pixels: Pixels, strength: float, rng: np.random.Generator) -> Pixels:
    noisy = pixels.astype(np.float64) + rng.normal(0, strength, pixels.shape)
    return np.clip(noisy, 0, 255).astype(np.uint8)


def _jpeg(pixels: Pixels, strength: float, rng: np.random.Generator) -> Pixels:
    ok, encoded = cv2.imencode(".jpg", pixels, [cv2.IMWRITE_JPEG_QUALITY, int(strength)])
    decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR) if ok else None
    return pixels if decoded is None else np.asarray(decoded, dtype=np.uint8)


def _low_resolution(pixels: Pixels, strength: float, rng: np.random.Generator) -> Pixels:
    h, w = pixels.shape[:2]
    small = cv2.resize(
        pixels, (max(1, int(w * strength)), max(1, int(h * strength))), interpolation=cv2.INTER_AREA
    )
    return np.asarray(cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR), dtype=np.uint8)


def _ramp(h: int, w: int, rng: np.random.Generator) -> NDArray[np.float64]:
    """0 to 1 across the page from a random side."""
    side = int(rng.integers(0, 4))
    across = np.linspace(0.0, 1.0, w)[None, :].repeat(h, axis=0)
    down = np.linspace(0.0, 1.0, h)[:, None].repeat(w, axis=1)
    return [across, 1 - across, down, 1 - down][side]


def _shadow(pixels: Pixels, strength: float, rng: np.random.Generator) -> Pixels:
    h, w = pixels.shape[:2]
    darker = 1.0 - strength * _ramp(h, w, rng) ** 1.5
    return np.clip(pixels * darker[..., None], 0, 255).astype(np.uint8)


def _glare(pixels: Pixels, strength: float, rng: np.random.Generator) -> Pixels:
    h, w = pixels.shape[:2]
    cy, cx = rng.uniform(0.2, 0.8) * h, rng.uniform(0.2, 0.8) * w
    spread = 0.22 * min(h, w)
    ys, xs = np.mgrid[0:h, 0:w]
    spot = np.exp(-((ys - cy) ** 2 + (xs - cx) ** 2) / (2 * spread**2))
    bright = pixels + (255.0 * strength * spot)[..., None] * (1 - pixels / 255.0)
    return np.asarray(np.clip(bright, 0, 255), dtype=np.uint8)


def _perspective_tilt(pixels: Pixels, strength: float, rng: np.random.Generator) -> Pixels:
    h, w = pixels.shape[:2]
    pull = strength * w
    source = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    target = np.array([[pull, 0], [w - pull, 0], [w, h], [0, h]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(source, target)
    warped = cv2.warpPerspective(pixels, matrix, (w, h), borderValue=PAPER)
    return np.asarray(warped, dtype=np.uint8)


def _rotation(pixels: Pixels, strength: float, rng: np.random.Generator) -> Pixels:
    h, w = pixels.shape[:2]
    sign = 1.0 if rng.random() < 0.5 else -1.0
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), sign * strength, 1.0)
    return np.asarray(cv2.warpAffine(pixels, matrix, (w, h), borderValue=PAPER), dtype=np.uint8)


def _crumpled_paper(pixels: Pixels, strength: float, rng: np.random.Generator) -> Pixels:
    h, w = pixels.shape[:2]
    fields = []
    for _ in range(2):  # a smooth random push in x and in y
        coarse = rng.uniform(-1, 1, (6, 4)).astype(np.float32)
        fields.append(cv2.resize(coarse, (w, h), interpolation=cv2.INTER_CUBIC))
    dx, dy = fields
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    moved = cv2.remap(
        pixels,
        xs + strength * dx,
        ys + strength * dy,
        cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=PAPER,
    )
    # Folds catch the light: shade by how steeply the paper bends.
    bend = np.abs(np.gradient(dx, axis=1)) + np.abs(np.gradient(dy, axis=0))
    shade = 1.0 - np.clip(bend * strength * 1.5, 0, 0.4)
    return np.asarray(np.clip(moved * shade[..., None], 0, 255), dtype=np.uint8)


DAMAGES: dict[str, Callable[[Pixels, float, np.random.Generator], Pixels]] = {
    "blur": _blur,
    "motion_blur": _motion_blur,
    "noise": _noise,
    "jpeg": _jpeg,
    "low_resolution": _low_resolution,
    "shadow": _shadow,
    "glare": _glare,
    "perspective_tilt": _perspective_tilt,
    "rotation": _rotation,
    "crumpled_paper": _crumpled_paper,
}


def apply_damage(
    image: Image.Image, kind: str, level: int, strengths: Sequence[float], seed: int
) -> Image.Image:
    """The image with one kind of damage at a level from 0 (none) to 5 (worst)."""
    if kind not in DAMAGES:
        raise ValueError(f"unknown damage kind {kind!r}; known: {', '.join(DAMAGE_KINDS)}")
    if not 0 <= level <= MAX_LEVEL:
        raise ValueError(f"damage level must be 0 to {MAX_LEVEL}, got {level}")
    if level == 0:
        return image.copy()
    if len(strengths) != MAX_LEVEL:
        raise ValueError(f"{kind} needs {MAX_LEVEL} strengths, got {len(strengths)}")
    pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)
    damaged = DAMAGES[kind](pixels, strengths[level - 1], np.random.default_rng(seed))
    return Image.fromarray(damaged)
