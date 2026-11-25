import json
import shutil
from pathlib import Path

import pytest

from reimbursement_council.cli.main import main
from tests.factories import REPO_CONFIG

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
CLAIMS = FIXTURES / "claims"


def run(tmp_path: Path, claim: Path, config_dir: Path = REPO_CONFIG) -> int:
    return main(
        [
            "run-claim",
            str(claim),
            "--reference",
            str(FIXTURES / "reference.json"),
            "--config-dir",
            str(config_dir),
            "--db",
            str(tmp_path / "c.sqlite"),
        ]
    )


def test_run_clean_claim(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = run(tmp_path, CLAIMS / "clean.claim.json")
    out = capsys.readouterr().out
    assert code == 0
    assert "lane: auto_approve" in out
    assert "outcome: complete" in out
    assert "payout: 135.00 SAR" in out
    assert "message (en): Your claim is approved. We will send you 135.00 SAR." in out
    assert "message (ar): " in out


def test_run_prescription_only_has_no_payout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(tmp_path, CLAIMS / "prescription_only.claim.json") == 0
    out = capsys.readouterr().out
    assert "lane: self_fix" in out and "payout: none" in out


def test_unknown_member_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    claim = json.loads((CLAIMS / "clean.claim.json").read_text(encoding="utf-8"))
    claim["member_id"] = "nobody"
    path = tmp_path / "unknown.claim.json"
    path.write_text(json.dumps(claim), encoding="utf-8")
    shutil.copy(CLAIMS / "clean.reading.json", tmp_path / "clean.reading.json")
    assert run(tmp_path, path) == 2
    assert "lane:" not in capsys.readouterr().out


def test_bad_config_exits_2(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    shutil.copytree(REPO_CONFIG, config_dir)
    (config_dir / "decision.yaml").write_text("hard_rule_confidence_floor: 5\n", encoding="utf-8")
    assert run(tmp_path, CLAIMS / "clean.claim.json", config_dir) == 2


def test_missing_claim_file_exits_2(tmp_path: Path) -> None:
    assert run(tmp_path, tmp_path / "missing.claim.json") == 2


def test_no_command_shows_usage_and_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([])
    assert exit_info.value.code == 2


def test_rejected_claim_shows_no_payout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(tmp_path, CLAIMS / "late.claim.json") == 0  # final review: misleading payout
    out = capsys.readouterr().out
    assert "lane: auto_reject" in out and "payout: none (rejected)" in out
