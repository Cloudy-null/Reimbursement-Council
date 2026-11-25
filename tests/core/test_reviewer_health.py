from datetime import UTC, datetime, timedelta

import pytest

from reimbursement_council.config.models import CaseReviewerConfig
from reimbursement_council.core.models.case_review import (
    CaseReview,
    GoldenResult,
    ReviewerHealth,
)
from reimbursement_council.core.reviewer_health import (
    after_golden_check,
    enable,
    health_report,
    is_usable,
    monitor_problems,
    record_review,
)
from tests.factories import repo_settings

NOW = datetime(2026, 11, 25, 3, 0, tzinfo=UTC)
MODEL, PROMPT = "qwen3-vl:8b", "1"


def config() -> CaseReviewerConfig:
    return repo_settings().decision.members.case_reviewer


def results(passed: int, total: int = 20) -> list[GoldenResult]:
    return [
        GoldenResult(
            name=f"case{i}",
            expected="good",
            status="used",
            problem=None,
            score=0.9,
            passed=i < passed,
        )
        for i in range(total)
    ]


def used(score: float) -> CaseReview:
    return CaseReview(status="used", score=score, model=MODEL, prompt_version=PROMPT)


def discarded() -> CaseReview:
    return CaseReview(status="discarded", problem="schema", model=MODEL, prompt_version=PROMPT)


def healthy() -> ReviewerHealth:
    return after_golden_check(ReviewerHealth(), results(20), config(), MODEL, PROMPT, NOW)


def test_a_new_reviewer_is_not_usable_until_checked() -> None:
    assert not is_usable(ReviewerHealth(), MODEL, PROMPT)
    assert is_usable(healthy(), MODEL, PROMPT)


def test_another_model_or_prompt_needs_a_new_check() -> None:
    assert not is_usable(healthy(), "other-model", PROMPT)
    assert not is_usable(healthy(), MODEL, "2")


def test_failing_the_golden_set_benches() -> None:
    health = after_golden_check(healthy(), results(10), config(), MODEL, PROMPT, NOW)
    assert health.status == "benched" and "golden" in (health.bench_reason or "")
    assert not is_usable(health, MODEL, PROMPT)


def test_a_pass_after_a_bench_does_not_re_enable_by_itself() -> None:
    benched = after_golden_check(healthy(), results(10), config(), MODEL, PROMPT, NOW)
    later = NOW + timedelta(minutes=5)
    checked = after_golden_check(benched, results(20), config(), MODEL, PROMPT, later)
    assert checked.status == "benched" and checked.last_check_passed


def test_a_person_enables_only_after_a_passing_check() -> None:
    benched = after_golden_check(healthy(), results(10), config(), MODEL, PROMPT, NOW)
    with pytest.raises(ValueError, match="check-reviewer"):
        enable(benched, MODEL, PROMPT)
    checked = after_golden_check(
        benched, results(20), config(), MODEL, PROMPT, NOW + timedelta(minutes=5)
    )
    with pytest.raises(ValueError, match="check-reviewer"):
        enable(checked, "other-model", PROMPT)
    enabled = enable(checked, MODEL, PROMPT)
    assert enabled.status == "healthy" and enabled.recent == []


def test_enabling_a_healthy_reviewer_is_refused() -> None:
    with pytest.raises(ValueError, match="not benched"):
        enable(healthy(), MODEL, PROMPT)


def test_too_many_discarded_answers_bench() -> None:
    health = healthy()
    for i in range(20):
        health = record_review(health, discarded() if i % 2 else used(0.1 * (i % 9)), config(), NOW)
    assert health.status == "benched" and "discarded" in (health.bench_reason or "")


def test_collapsed_scores_bench() -> None:
    health = healthy()
    for _ in range(config().monitor_min_votes):
        health = record_review(health, used(0.95), config(), NOW)
    assert health.status == "benched" and "collapsed" in (health.bench_reason or "")


def test_varied_scores_stay_healthy_and_window_is_kept_short() -> None:
    health = healthy()
    for i in range(config().monitor_window + 15):
        health = record_review(health, used((i % 10) / 10), config(), NOW)
    assert health.status == "healthy"
    assert len(health.recent) == config().monitor_window


def test_monitors_wait_for_enough_answers() -> None:
    assert monitor_problems([], config()) == []
    health = record_review(healthy(), discarded(), config(), NOW)
    assert health.status == "healthy"


def test_timeouts_do_not_feed_the_monitors() -> None:
    timeout = CaseReview(status="skipped", problem="timeout", model=MODEL, prompt_version=PROMPT)
    assert record_review(healthy(), timeout, config(), NOW) == healthy()


def test_health_report_states() -> None:
    assert health_report(healthy(), False, MODEL, PROMPT).state == "off"
    assert health_report(ReviewerHealth(), True, MODEL, PROMPT).state == "unchecked"
    report = health_report(healthy(), True, MODEL, PROMPT)
    assert report.state == "healthy" and report.golden_pass_rate == 1.0
    benched = after_golden_check(healthy(), results(0), config(), MODEL, PROMPT, NOW)
    report = health_report(benched, True, MODEL, PROMPT)
    assert report.state == "benched" and report.bench_reason
