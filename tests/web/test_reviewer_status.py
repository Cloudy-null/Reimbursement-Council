"""The numbers page names the AI reviewer's state in one line."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from reimbursement_council.core.models.case_review import HealthReport
from reimbursement_council.web.context import WebContext
from reimbursement_council.web.i18n import text_for
from reimbursement_council.web.reviewer_check import reviewer_status_line


def health(state: str, reason: str | None = None) -> HealthReport:
    return HealthReport(
        state=state,  # type: ignore[arg-type]
        last_check_at=datetime(2026, 11, 25, 18, 0, tzinfo=UTC),
        golden_pass_rate=0.85,
        bench_reason=reason,
        model="m",
        prompt_version="3",
        discarded_rate=None,
        score_spread=None,
        recent_answers=0,
    )


def test_a_benched_reviewer_shows_its_check_time_score_and_reason() -> None:
    line = reviewer_status_line(health("benched", "golden set pass rate 0.85"), text_for("en"))
    assert line.startswith("AI reviewer: benched")
    assert "2026-11-25 18:00 UTC" in line and "0.85" in line and "pass rate" in line


def test_no_reviewer_reads_off_in_both_languages() -> None:
    assert reviewer_status_line(None, text_for("en")) == "AI reviewer: off"
    assert "متوقف" in reviewer_status_line(None, text_for("ar"))


def test_the_numbers_page_shows_the_line(web: tuple[TestClient, WebContext]) -> None:
    page = web[0].get("/metrics").text
    assert 'id="reviewer-status"' in page and "AI reviewer: off" in page
