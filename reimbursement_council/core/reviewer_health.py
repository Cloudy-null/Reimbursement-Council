"""Health of the AI case reviewer and its circuit breaker. Pure: the state is stored by an
adapter (adapters/reviewer_health_store.py) and the model is called by the pipeline.

A reviewer is used only when it passed the golden set with the model and prompt version in
config. Failing the golden set, too many discarded answers, or scores that collapse to one
value bench it. A benched reviewer never comes back by itself: a person runs check-reviewer,
and when that passes, reviewer-enable.
"""

import statistics
from collections.abc import Sequence
from datetime import datetime

from reimbursement_council.config.models import CaseReviewerConfig
from reimbursement_council.core.models.case_review import (
    CaseReview,
    GoldenCase,
    GoldenResult,
    HealthReport,
    RecentReview,
    ReviewerHealth,
)


def is_usable(health: ReviewerHealth, model: str, prompt_version: str) -> bool:
    return (
        health.status == "healthy"
        and health.model == model
        and health.prompt_version == prompt_version
    )


def golden_result(case: GoldenCase, review: CaseReview, config: CaseReviewerConfig) -> GoldenResult:
    """A good case passes with a used score at or above golden_good_min_score, a bad case
    with one at or below golden_bad_max_score. A discarded or missing answer fails."""
    score = review.score if review.status == "used" else None
    if score is None:
        passed = False
    elif case.expected == "good":
        passed = score >= config.golden_good_min_score
    else:
        passed = score <= config.golden_bad_max_score
    return GoldenResult(
        name=case.name,
        expected=case.expected,
        status=review.status,
        problem=review.problem,
        score=score,
        passed=passed,
    )


def golden_pass_rate(results: Sequence[GoldenResult]) -> float:
    if not results:
        raise ValueError("the golden set is empty")
    return sum(result.passed for result in results) / len(results)


def _bench(health: ReviewerHealth, reason: str, now: datetime) -> ReviewerHealth:
    if health.status == "benched":
        return health
    return health.model_copy(
        update={"status": "benched", "bench_reason": reason, "benched_at": now}
    )


def after_golden_check(
    health: ReviewerHealth,
    results: Sequence[GoldenResult],
    config: CaseReviewerConfig,
    model: str,
    prompt_version: str,
    now: datetime,
) -> ReviewerHealth:
    """Record a golden run. A fail benches. A pass makes an unchecked or healthy reviewer
    healthy, but a benched one stays benched until a person enables it."""
    rate = golden_pass_rate(results)
    passed = rate >= config.golden_pass_rate
    checked = health.model_copy(
        update={
            "last_check_at": now,
            "last_check_passed": passed,
            "golden_pass_rate": rate,
            "model": model,
            "prompt_version": prompt_version,
        }
    )
    if not passed:
        return _bench(
            checked,
            f"golden set pass rate {rate:.2f} is below {config.golden_pass_rate:.2f}",
            now,
        )
    if checked.status == "benched":
        return checked
    return checked.model_copy(update={"status": "healthy", "bench_reason": None})


def monitor_numbers(
    recent: Sequence[RecentReview],
) -> tuple[float | None, float | None]:
    """(share of discarded answers, standard deviation of used scores); None when empty."""
    counted = [r for r in recent if r.status in ("used", "discarded")]
    discarded_rate = (
        sum(r.status == "discarded" for r in counted) / len(counted) if counted else None
    )
    scores = [r.score for r in recent if r.status == "used" and r.score is not None]
    spread = statistics.pstdev(scores) if len(scores) >= 2 else None
    return discarded_rate, spread


def monitor_problems(recent: Sequence[RecentReview], config: CaseReviewerConfig) -> list[str]:
    """Why the recent answers bench the reviewer. Empty while there are too few answers."""
    problems: list[str] = []
    counted = [r for r in recent if r.status in ("used", "discarded")]
    used = [r for r in recent if r.status == "used"]
    discarded_rate, spread = monitor_numbers(recent)
    rate_limit, spread_floor = config.max_discarded_rate, config.min_score_spread
    enough_answers = len(counted) >= config.monitor_min_votes
    if enough_answers and discarded_rate is not None and discarded_rate > rate_limit:
        problems.append(f"discarded answers {discarded_rate:.2f} are above {rate_limit:.2f}")
    enough_scores = len(used) >= config.monitor_min_votes
    if enough_scores and spread is not None and spread < spread_floor:
        problems.append(f"scores collapsed: spread {spread:.3f} is below {spread_floor:.3f}")
    return problems


def record_review(
    health: ReviewerHealth, review: CaseReview, config: CaseReviewerConfig, now: datetime
) -> ReviewerHealth:
    """Add one answer to the rolling window and bench the reviewer if a monitor trips."""
    if review.status not in ("used", "discarded"):
        return health  # no answer (timeout, error, benched): nothing for the monitors
    recent = [*health.recent, RecentReview(status=review.status, score=review.score)]
    recent = recent[-config.monitor_window :]
    updated = health.model_copy(update={"recent": recent})
    problems = monitor_problems(recent, config)
    if problems and updated.status == "healthy":
        return _bench(updated, "; ".join(problems), now)
    return updated


def enable(health: ReviewerHealth, model: str, prompt_version: str) -> ReviewerHealth:
    """A person turns a benched reviewer back on. Only after a golden check that passed with
    this model and prompt version, run after it was benched. The window starts empty."""
    if health.status != "benched":
        raise ValueError(f"the reviewer is {health.status}, not benched: nothing to enable")
    fresh = (
        health.last_check_passed is True
        and health.model == model
        and health.prompt_version == prompt_version
        and health.last_check_at is not None
        and health.benched_at is not None
        and health.last_check_at > health.benched_at
    )
    if not fresh:
        raise ValueError(
            "run check-reviewer first: enabling needs a passing golden check after the bench, "
            f"with model {model} and prompt version {prompt_version}"
        )
    return health.model_copy(
        update={"status": "healthy", "bench_reason": None, "benched_at": None, "recent": []}
    )


def health_report(
    health: ReviewerHealth, enabled: bool, model: str, prompt_version: str
) -> HealthReport:
    """What a screen shows about the reviewer (off, unchecked, healthy or benched)."""
    if not enabled:
        state = "off"
    elif health.status == "benched":
        state = "benched"
    elif is_usable(health, model, prompt_version):
        state = "healthy"
    else:
        state = "unchecked"
    discarded_rate, spread = monitor_numbers(health.recent)
    return HealthReport(
        state=state,
        last_check_at=health.last_check_at,
        golden_pass_rate=health.golden_pass_rate,
        bench_reason=health.bench_reason,
        model=model,
        prompt_version=prompt_version,
        discarded_rate=discarded_rate,
        score_spread=spread,
        recent_answers=len(health.recent),
    )
