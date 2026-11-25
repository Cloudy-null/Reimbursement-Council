"""Load the AI case reviewer's golden set: one JSON file per case in tests/golden/.

The golden set is for checking the reviewer, never for tuning it (tests/golden/README.md).
Every file is validated; a bad file stops the check instead of being skipped.
"""

from pathlib import Path

from pydantic import ValidationError

from reimbursement_council.core.models.case_review import GoldenCase

GOLDEN_DIR = Path(__file__).resolve().parents[2] / "tests" / "golden"


def load_golden_set(folder: Path = GOLDEN_DIR) -> list[GoldenCase]:
    paths = sorted(folder.glob("*.json"))
    if not paths:
        raise FileNotFoundError(f"no golden cases in {folder}")
    cases: list[GoldenCase] = []
    for path in paths:
        try:
            case = GoldenCase.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError as error:
            raise ValueError(f"golden case {path.name} is not valid: {error}") from error
        if case.name != path.stem:
            raise ValueError(f"golden case {path.name} is named {case.name!r}, not {path.stem!r}")
        cases.append(case)
    return cases
