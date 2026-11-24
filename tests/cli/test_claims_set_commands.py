import json
import logging
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from reimbursement_council.cli import claims_set
from reimbursement_council.cli.main import main
from reimbursement_council.config.loader import CONFIG_FILES
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
    assert len(list(out.glob("claim_4_????.png"))) == 6  # one receipt each
    truth = json.loads(next(out.glob("*.truth.json")).read_text(encoding="utf-8"))
    assert {"should_pay", "correct_payout", "defects", "document_kinds", "expected_lane"} <= set(
        truth
    )


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
    assert {"document_kind_accuracy", "expected_lane_match_count"} <= set(results["metrics"])
    first = results["rows"][0]
    assert first["kinds_true"] and first["kinds_read"].keys() == first["kinds_true"].keys()
    assert results["cross_checks"] is True


def test_run_set_can_turn_cross_checks_off(tmp_path: Path) -> None:
    out = tmp_path / "set"
    run(
        "make-claims",
        "--count",
        "3",
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
        "--cross-checks",
        "off",
        "--config-dir",
        str(REPO_CONFIG),
        "--ocr-cache",
        str(tmp_path / "c"),
    )
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert code == 0 and results["cross_checks"] is False
    assert not any(row["cross_check_failed"] for row in results["rows"])


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


def calibration_rows() -> list[dict[str, object]]:
    return [
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
            "hard_rule_failed": False,
            "damage": "none",
        }
        for i, s in enumerate([0.2, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.97, 0.99])
    ]


def fit(tmp_path: Path, rows: list[dict[str, object]]) -> dict[str, Any]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    results = tmp_path / "results.json"
    results.write_text(json.dumps({"rows": rows, "metrics": {}}), encoding="utf-8")
    config = tmp_path / "config"
    config.mkdir()
    for name in CONFIG_FILES:
        (config / name).write_bytes((REPO_CONFIG / name).read_bytes())
    assert run("fit-calibration", str(results), "--config-dir", str(config)) == 0
    params: dict[str, Any] = yaml.safe_load((config / "calibration.yaml").read_text("utf-8"))
    return params


def test_make_claims_refuses_a_folder_that_is_not_empty(tmp_path: Path) -> None:
    # Mixing two sets in one folder judges one seed's claims against another seed's members.
    out = tmp_path / "set"
    make_set(out, count=2)
    args = ["make-claims", "--count", "2", "--seed", "5", "--out", str(out)]
    assert run(*args, "--config-dir", str(REPO_CONFIG)) == 2
    assert len(list(out.glob("*.claim.json"))) == 2


def test_make_claims_writes_a_manifest_and_truth_names_its_claim(tmp_path: Path) -> None:
    out = tmp_path / "set"
    make_set(out, count=2)
    manifest = json.loads((out / "set.json").read_text(encoding="utf-8"))
    assert manifest["seed"] == 4 and manifest["count"] == 2 and manifest["config_version"]
    for truth_path in out.glob("*.truth.json"):
        truth = json.loads(truth_path.read_text(encoding="utf-8"))
        claim_path = truth_path.with_name(truth_path.name.replace(".truth.json", ".claim.json"))
        claim = json.loads(claim_path.read_text(encoding="utf-8"))
        assert truth["claim_id"] == claim["claim_id"]


def test_run_set_refuses_a_set_with_extra_claims(tmp_path: Path) -> None:
    out, other = tmp_path / "set", tmp_path / "other"
    make_set(out, count=2)
    make_set(other, count=3)
    for path in other.glob("claim_4_0002.*"):
        (out / path.name).write_bytes(path.read_bytes())
    assert run_set(out, tmp_path / "c") == 2


def test_run_set_refuses_an_empty_folder(tmp_path: Path) -> None:
    out = tmp_path / "empty"
    out.mkdir()
    assert run_set(out, tmp_path / "c") == 2


def test_fit_calibration_writes_params(tmp_path: Path) -> None:
    params = fit(tmp_path, calibration_rows())
    assert params["method"] == "platt" and params["a"] > 0


def test_fit_calibration_leaves_out_claims_a_hard_rule_rejected(tmp_path: Path) -> None:
    rejected = [
        row
        | {
            "name": f"r{i}",
            "lane": "auto_reject",
            "payout_calculated": None,
            "should_pay": False,
            "correct_payout": 0,
            "hard_rule_failed": True,
            "p_good": 0.99,
            "combined_score": 0.99,
        }
        for i, row in enumerate(calibration_rows()[:5])
    ]
    alone = fit(tmp_path / "a", calibration_rows())
    mixed = fit(tmp_path / "b", calibration_rows() + rejected)
    assert (mixed["a"], mixed["b"]) == (alone["a"], alone["b"])


def test_make_claims_writes_one_png_per_document(tmp_path: Path) -> None:
    out = tmp_path / "set"
    run(
        "make-claims",
        "--count",
        "12",
        "--seed",
        "4",
        "--out",
        str(out),
        "--config-dir",
        str(REPO_CONFIG),
    )
    claims = [json.loads(p.read_text(encoding="utf-8")) for p in out.glob("*.claim.json")]
    documents = [d for c in claims for d in c["documents"]]
    assert len(list(out.glob("*.png"))) == len(documents) > len(claims)
    assert all((out / d["file_path"]).is_file() for d in documents)


def test_export_set_writes_one_valid_file_per_claim_and_a_summary(tmp_path: Path) -> None:
    out = tmp_path / "set"
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
    exported = tmp_path / "export"
    code = run(
        "export-set",
        str(out),
        "--out",
        str(exported),
        "--reader",
        "qr_only",
        "--config-dir",
        str(REPO_CONFIG),
        "--ocr-cache",
        str(tmp_path / "c"),
    )
    summary = json.loads((exported / "summary.json").read_text(encoding="utf-8"))
    assert (
        code == 0 and summary["claims"] == 6 and summary["valid"] == 6 and summary["invalid"] == 0
    )
    files = [p for p in exported.glob("*.json") if p.name != "summary.json"]
    assert len(files) == 6
    first = json.loads(files[0].read_text(encoding="utf-8"))
    assert first["schema_version"] == "1.0" and "decision" in first
