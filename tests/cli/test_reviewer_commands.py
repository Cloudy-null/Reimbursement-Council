"""check-reviewer, reviewer-enable, reviewer-status and run-set with the reviewer on, all with
fake models (the real model is never called)."""

import json
from pathlib import Path
from typing import Any

import pytest

from reimbursement_council.adapters.reviewer_health_store import ReviewerHealthStore
from reimbursement_council.cli import reviewer as reviewer_module
from reimbursement_council.cli import run_set as run_set_module
from reimbursement_council.cli.main import main
from reimbursement_council.config.models import Settings
from reimbursement_council.pipeline.case_review import CaseReviewerService
from reimbursement_council.web.reviewer_check import reviewer_health, start_reviewer_check
from tests.cli.test_claims_set_commands import make_set, run_set
from tests.factories import REPO_CONFIG
from tests.pipeline.test_case_review import FakeModel, enabled_settings, right, wrong


class Models:
    """Which fake answers the golden check; the live model always answers like right()."""

    def __init__(self) -> None:
        self.check = FakeModel(right)


@pytest.fixture
def models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Models:
    chosen = Models()

    def fake_reviewer(settings: Settings, data_dir: Path) -> CaseReviewerService:
        return CaseReviewerService(
            settings,
            live=FakeModel(right),
            check=chosen.check,
            health=ReviewerHealthStore(tmp_path / "data" / "reviewer" / "health.json"),
        )

    monkeypatch.setattr(reviewer_module, "make_case_reviewer", fake_reviewer)
    monkeypatch.setattr(run_set_module, "make_case_reviewer", fake_reviewer)
    return chosen


def command(name: str) -> int:
    return main([name, "--config-dir", str(REPO_CONFIG), "--data-dir", "unused"])


def test_check_then_status(models: Models, capsys: pytest.CaptureFixture[str]) -> None:
    assert command("check-reviewer") == 0
    assert "golden pass rate 1.00" in capsys.readouterr().out
    assert command("reviewer-status") == 0
    status: dict[str, Any] = json.loads(capsys.readouterr().out)
    assert status["state"] == "healthy"  # on in the repo config and checked
    assert status["golden_pass_rate"] == 1.0


def test_a_benched_reviewer_needs_a_passing_check_then_a_person(
    models: Models, capsys: pytest.CaptureFixture[str]
) -> None:
    models.check = FakeModel(wrong)
    assert command("check-reviewer") == 1
    assert command("reviewer-enable") == 2  # refused: the last check failed
    models.check = FakeModel(right)
    assert command("check-reviewer") == 0
    assert "run reviewer-enable" in capsys.readouterr().out
    assert command("reviewer-enable") == 0
    assert "healthy" in capsys.readouterr().out


def test_run_set_can_turn_the_reviewer_on(models: Models, tmp_path: Path) -> None:
    out = tmp_path / "set"
    make_set(out, count=4)
    assert run_set(out, tmp_path / "c", "--set", "members.case_reviewer.enabled=true") == 0
    report = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert all(row["reviewer_status"] for row in report["rows"])
    assert sum(report["reviewer_statuses"].values()) == 4


def test_run_set_without_the_reviewer_records_nothing(models: Models, tmp_path: Path) -> None:
    out = tmp_path / "set"
    make_set(out, count=2)
    assert run_set(out, tmp_path / "c", "--set", "members.case_reviewer.enabled=false") == 0
    report = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert report["reviewer_statuses"] == {}
    assert all(row["reviewer_status"] is None for row in report["rows"])


def test_startup_check_runs_in_the_background(tmp_path: Path) -> None:
    reviewer = CaseReviewerService(
        enabled_settings(),
        live=FakeModel(right),
        check=FakeModel(right),
        health=ReviewerHealthStore(tmp_path / "health.json"),
    )
    start_reviewer_check(reviewer).join(timeout=30)
    assert reviewer.health().state == "healthy"


def test_startup_check_errors_are_only_logged(tmp_path: Path) -> None:
    reviewer = CaseReviewerService(
        enabled_settings(),
        live=FakeModel(right),
        check=FakeModel(right),
        health=ReviewerHealthStore(tmp_path / "health.json"),
        golden_dir=tmp_path / "no-golden-set",
    )
    start_reviewer_check(reviewer).join(timeout=30)
    assert reviewer.health().state == "unchecked"


def test_web_layer_gets_the_health(tmp_path: Path) -> None:
    from reimbursement_council.adapters.storage import ClaimStore
    from reimbursement_council.web.context import WebContext

    reviewer = CaseReviewerService(
        enabled_settings(),
        live=FakeModel(right),
        check=FakeModel(right),
        health=ReviewerHealthStore(tmp_path / "health.json"),
    )
    ctx = WebContext(
        settings=enabled_settings(),
        reference=None,  # type: ignore[arg-type]
        store=ClaimStore(tmp_path / "web.sqlite"),
        reader_for=lambda document: None,  # type: ignore[arg-type, return-value]
        uploads=tmp_path,
        samples=tmp_path,
        results_root=tmp_path,
    )
    assert reviewer_health(ctx) is None
    ctx.case_reviewer = reviewer
    report = reviewer_health(ctx)
    assert report is not None and report.state == "unchecked"
