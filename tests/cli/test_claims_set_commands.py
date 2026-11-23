import json
from pathlib import Path

import pytest
import yaml

from reimbursement_council.cli.main import main
from tests.factories import REPO_CONFIG


def run(*argv: str) -> int:
    return main(list(argv))


def test_make_claims_writes_a_runnable_folder(tmp_path: Path) -> None:
    out = tmp_path / "set"
    assert (
        run(
            "make-claims",
            "--count",
            "6",
            "--seed",
            "4",
            "--out",
            str(out),
            "--config-dir",
            str(REPO_CONFIG),
        )
        == 0
    )
    assert (out / "reference.json").is_file()
    assert len(list(out.glob("*.claim.json"))) == 6
    assert len(list(out.glob("*.png"))) == 6
    truth = json.loads(next(out.glob("*.truth.json")).read_text(encoding="utf-8"))
    assert {"should_pay", "correct_payout", "defects"} <= set(truth)


def test_run_set_scores_every_claim(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "set"
    run(
        "make-claims",
        "--count",
        "8",
        "--seed",
        "4",
        "--out",
        str(out),
        "--config-dir",
        str(REPO_CONFIG),
    )
    code = run(
        "run-set",
        str(out),
        "--reader",
        "qr_only",
        "--config-dir",
        str(REPO_CONFIG),
        "--ocr-cache",
        str(tmp_path / "c"),
    )
    assert code == 0
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert len(results["rows"]) == 8
    assert {"automation_rate", "auto_approve_precision", "ece", "total_cost_sar"} <= set(
        results["metrics"]
    )
    assert "automation_rate" in capsys.readouterr().out


def test_fit_calibration_writes_params(tmp_path: Path) -> None:
    rows = [
        {
            "name": f"c{i}",
            "lane": "auto_approve",
            "outcome": "complete",
            "payout_calculated": 15525 if i % 3 else 900,
            "p_good": s,
            "combined_score": s,
            "should_pay": True,
            "correct_payout": 15525,
            "defects": [],
        }
        for i, s in enumerate([0.2, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.97, 0.99])
    ]
    results = tmp_path / "results.json"
    results.write_text(json.dumps({"rows": rows, "metrics": {}}), encoding="utf-8")
    config = tmp_path / "config"
    config.mkdir()
    for name in ("decision.yaml", "messages.yaml", "policy.yaml", "prices.yaml"):
        (config / name).write_bytes((REPO_CONFIG / name).read_bytes())
    assert run("fit-calibration", str(results), "--config-dir", str(config)) == 0
    params = yaml.safe_load((config / "calibration.yaml").read_text(encoding="utf-8"))
    assert params["method"] == "platt" and params["a"] > 0
