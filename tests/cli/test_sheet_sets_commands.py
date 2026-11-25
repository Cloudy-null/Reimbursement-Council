import json
from pathlib import Path

import pytest

from reimbursement_council.cli.main import main
from reimbursement_council.core.models.claim import Claim
from tests.factories import REPO_CONFIG


def _check_folder(out: Path, count: int, kind: str) -> list[dict[str, object]]:
    claims = sorted(out.glob("*.claim.json"))
    manifest = json.loads((out / "set.json").read_text(encoding="utf-8"))
    assert manifest["count"] == len(claims) == count
    assert manifest["label"] == "real-derived synthetic" and manifest["kind"] == kind
    assert (out / "reference.json").is_file()
    truths = []
    for path in claims:
        claim = Claim.model_validate_json(path.read_text(encoding="utf-8"))
        for document in claim.documents:
            assert (out / document.file_path).is_file()
        truth_path = path.with_name(path.name.replace(".claim.json", ".truth.json"))
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        assert truth["claim_id"] == claim.claim_id
        assert {"should_pay", "correct_payout", "defects", "damage", "fix", "scenario"} <= set(
            truth
        )
        if truth["fix"]:
            assert (out / truth["fix"]["file"]).is_file()
        truths.append(truth)
    return truths


@pytest.mark.parametrize(("command", "count", "kind"), [("make-optical-claims", 20, "optical")])
def test_sheet_set_commands_write_the_make_claims_format(
    tmp_path: Path, command: str, count: int, kind: str
) -> None:
    out = tmp_path / kind
    assert main([command, str(out), "--seed", "2", "--config-dir", str(REPO_CONFIG)]) == 0
    _check_folder(out, count, kind)
    # a folder that is not empty is refused
    assert main([command, str(out), "--config-dir", str(REPO_CONFIG)]) == 2
