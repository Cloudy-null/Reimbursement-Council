import cv2
import numpy as np
import pytest
from PIL import Image

from reimbursement_council.adapters.damage_suite import DAMAGE_KINDS, apply_damage
from reimbursement_council.adapters.sheet_drawing import draw_sheet
from reimbursement_council.synthetic.dental_claims import make_dental_set
from tests.factories import repo_settings


def _page() -> Image.Image:
    import io

    sheet = make_dental_set(1, repo_settings()).cases[0].documents[0].sheet
    return Image.open(io.BytesIO(draw_sheet(sheet).png)).convert("RGB")


# Moving the page: pixel by pixel, a small shift already changes every letter, so compare
# the pages blurred to coarse shapes instead.
MOVES_THE_PAGE = {"perspective_tilt", "rotation", "crumpled_paper"}


def _change(a: Image.Image, b: Image.Image, coarse: bool = False) -> float:
    first, second = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    if coarse:
        first = cv2.GaussianBlur(first, (0, 0), 20)
        second = cv2.GaussianBlur(second, (0, 0), 20)
    return float(np.abs(first - second).mean())


def test_config_names_every_damage_kind_with_five_levels() -> None:
    suite = repo_settings().synthetic.damage_suite
    assert set(suite) == set(DAMAGE_KINDS)
    assert all(len(levels) == 5 for levels in suite.values())


@pytest.mark.parametrize("kind", DAMAGE_KINDS)
def test_more_damage_as_the_level_rises(kind: str) -> None:
    page = _page()
    strengths = repo_settings().synthetic.damage_suite[kind]
    assert _change(page, apply_damage(page, kind, 0, strengths, seed=3)) == 0.0
    changes = [
        _change(page, apply_damage(page, kind, level, strengths, 3), kind in MOVES_THE_PAGE)
        for level in range(1, 6)
    ]
    assert changes[0] > 0
    assert changes == sorted(changes) and changes[-1] > changes[0], changes
    damaged = apply_damage(page, kind, 4, strengths, seed=3)
    assert damaged.size == page.size
    assert damaged.tobytes() == apply_damage(page, kind, 4, strengths, seed=3).tobytes()


def test_bad_kind_or_level_is_refused() -> None:
    page = _page()
    with pytest.raises(ValueError, match="unknown damage"):
        apply_damage(page, "coffee_stain", 1, [1, 2, 3, 4, 5], 0)
    with pytest.raises(ValueError, match="0 to 5"):
        apply_damage(page, "blur", 6, [1, 2, 3, 4, 5], 0)


def test_config_refuses_a_kind_without_five_levels() -> None:
    from pydantic import ValidationError

    from reimbursement_council.config.models import SyntheticConfig

    with pytest.raises(ValidationError, match="5 strengths"):
        SyntheticConfig(qr_share=0.5, defect_weights={"clean": 1}, damage_suite={"blur": [1.0]})
