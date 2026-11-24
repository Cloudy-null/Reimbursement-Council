import json
import logging
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from reimbursement_council.cli import claims_set
from reimbursement_council.cli.main import main
from reimbursement_council.core.models.claim import Claim
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


def make_set(out: Path, count: int = 8) -> None:
    args = ["make-claims", "--count", str(count), "--seed", "4", "--out", str(out)]
    assert run(*args, "--config-dir", str(REPO_CONFIG)) == 0


def run_set(out: Path, cache: Path, *extra: str) -> int:
    args = ["run-set", str(out), "--reader", "qr_only", "--config-dir", str(REPO_CONFIG)]
    return run(*args, "--ocr-cache", str(cache), *extra)


def result_rows(out: Path, name: str = "results.json") -> list[dict[str, object]]:
    rows: list[dict[str, object]] = json.loads((out / name).read_text(encoding="utf-8"))["rows"]
    return rows


def test_resume_runs_only_the_claims_without_a_stored_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clean, broken = tmp_path / "clean", tmp_path / "broken"
    make_set(clean)
    make_set(broken)
    assert run_set(clean, tmp_path / "c") == 0

    real = claims_set.process_claim
    calls: list[str] = []

    def dies_after_five(claim: Claim, *args: Any, **kwargs: Any) -> Any:
        if len(calls) == 5:
            raise RuntimeError("process killed")
        calls.append(claim.claim_id)
        return real(claim, *args, **kwargs)

    monkeypatch.setattr(claims_set, "process_claim", dies_after_five)
    with pytest.raises(RuntimeError):
        run_set(broken, tmp_path / "c")

    calls.clear()
    monkeypatch.setattr(
        claims_set, "process_claim", lambda c, *a, **k: calls.append(c) or real(c, *a, **k)
    )
    assert run_set(broken, tmp_path / "c", "--resume") == 0
    assert len(calls) == 3
    assert result_rows(broken) == result_rows(clean)


def test_resume_refuses_a_run_made_with_other_settings(tmp_path: Path) -> None:
    out = tmp_path / "set"
    make_set(out, count=2)
    assert run_set(out, tmp_path / "c") == 0
    args = ["run-set", str(out), "--reader", "easyocr", "--config-dir", str(REPO_CONFIG)]
    assert run(*args, "--ocr-cache", str(tmp_path / "c"), "--resume") == 2


def test_each_claim_logs_one_finish_line_with_timings(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    out = tmp_path / "set"
    make_set(out, count=3)
    with caplog.at_level(logging.INFO):
        assert run_set(out, tmp_path / "c") == 0
    finished = [r.getMessage() for r in caplog.records if r.name.endswith("process_claim")]
    assert len(finished) == 3
    assert all(re.search(r"read \d+\.\d+s, total \d+\.\d+s$", line) for line in finished)


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
