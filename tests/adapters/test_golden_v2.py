"""The v2 golden set loads with the normal loader and its two folders stay apart."""

from pathlib import Path

import pytest

from reimbursement_council.adapters.golden_set import load_golden_set
from reimbursement_council.core.models.case_review import GoldenCase

GOLDEN_V2 = Path(__file__).resolve().parents[1] / "golden_v2"


@pytest.mark.parametrize("folder", ["dev", "heldout"])
def test_each_folder_has_twenty_good_and_bad_cases(folder: str) -> None:
    cases = load_golden_set(GOLDEN_V2 / folder)
    assert len(cases) == 20
    assert {case.expected for case in cases} == {"good", "bad"}


def test_no_case_name_is_shared_between_dev_and_heldout() -> None:
    dev: list[GoldenCase] = load_golden_set(GOLDEN_V2 / "dev")
    heldout: list[GoldenCase] = load_golden_set(GOLDEN_V2 / "heldout")
    assert not {case.name for case in dev} & {case.name for case in heldout}
