"""Run the AI case reviewer on one claim, and its golden check. The model call and the health
file are adapters handed in; what the answer means is decided in core.

The council always decides first without the reviewer. The reviewer is asked only when it is
healthy, and its answer goes through core/decision/reviewer_guard.py, which lets it do one
thing only: send a claim that would be auto approved to a person.
"""

import logging
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from reimbursement_council.adapters.case_reviewer_model import (
    LocalCaseReviewer,
    ReviewerTimeoutError,
)
from reimbursement_council.adapters.golden_set import GOLDEN_DIR, load_golden_set
from reimbursement_council.adapters.local_model import LocalModelError
from reimbursement_council.adapters.reviewer_health_store import HEALTH_FILE, ReviewerHealthStore
from reimbursement_council.config.models import CaseReviewerConfig, Settings
from reimbursement_council.core.council.case_reviewer import (
    answer_schema,
    check_answer,
    not_used,
    review_vote,
)
from reimbursement_council.core.council.case_reviewer_summary import (
    SYSTEM_PROMPT,
    build_summary,
    render_prompt,
)
from reimbursement_council.core.decision.reviewer_guard import (
    DecideLane,
    GuardedDecision,
    apply_reviewer,
)
from reimbursement_council.core.models.case import ClaimCase
from reimbursement_council.core.models.case_review import (
    CaseReview,
    GoldenResult,
    HealthReport,
    ReviewerHealth,
    ReviewSummary,
)
from reimbursement_council.core.models.common import Lane
from reimbursement_council.core.models.decision import Vote
from reimbursement_council.core.reviewer_health import (
    after_golden_check,
    enable,
    golden_result,
    health_report,
    is_usable,
    record_review,
)

logger = logging.getLogger(__name__)


class ReviewerModel(Protocol):
    @property
    def name(self) -> str: ...

    def review(self, prompt: str, system: str, schema: dict[str, Any]) -> str: ...


class CaseReviewerService:
    """live: the model with the short timeout. check: the same model with the golden check
    timeout. health: where the health state is kept."""

    def __init__(
        self,
        settings: Settings,
        live: ReviewerModel,
        check: ReviewerModel,
        health: ReviewerHealthStore,
        golden_dir: Path = GOLDEN_DIR,
    ) -> None:
        self.settings = settings
        self.live = live
        self.check_model = check
        self.health_store = health
        self.golden_dir = golden_dir
        self.prompt_version = settings.local_model.reviewer_prompt_version

    @property
    def config(self) -> CaseReviewerConfig:
        return self.settings.decision.members.case_reviewer

    def _ask(self, model: ReviewerModel, summary: ReviewSummary) -> CaseReview:
        """One answer, checked. Timeouts and errors give a skipped review."""
        name = model.name
        try:
            text = model.review(render_prompt(summary), SYSTEM_PROMPT, answer_schema(self.config))
        except ReviewerTimeoutError as error:
            logger.warning("claim %s: case reviewer timed out: %s", summary.claim_id, error)
            return not_used(
                "skipped", "timeout", name, self.prompt_version, "No answer in time; not used."
            )
        except LocalModelError as error:
            logger.warning("claim %s: case reviewer failed: %s", summary.claim_id, error)
            return not_used(
                "skipped", "error", name, self.prompt_version, "The model failed; not used."
            )
        return check_answer(text, summary, self.config, name, self.prompt_version)

    def review(
        self, case: ClaimCase, votes: Sequence[Vote], council_lane: Lane, now: datetime
    ) -> CaseReview:
        name, version = self.live.name, self.prompt_version
        claim_id = case.claim.claim_id
        if council_lane not in self.config.review_lanes:
            return not_used(
                "skipped", "lane_not_reviewed", name, version, f"Not asked for {council_lane}."
            )
        health = self.health_store.load()
        if health.status == "benched":
            return not_used("benched", "benched", name, version, "The reviewer is benched.")
        if not is_usable(health, name, version):
            return not_used(
                "skipped", "unchecked", name, version, "No passing golden check for this model."
            )
        review = self._ask(self.live, build_summary(case, votes))
        after = self.health_store.update(
            lambda current: record_review(current, review, self.config, now)
        )
        logger.info(
            "claim %s: case reviewer %s%s, score %s",
            claim_id,
            review.status,
            f" ({review.problem})" if review.problem else "",
            "none" if review.score is None else f"{review.score:.2f}",
        )
        if after.status == "benched":
            logger.error("case reviewer benched: %s", after.bench_reason)
            return review.model_copy(
                update={
                    "status": "benched",
                    "problem": "benched",
                    "score": None,
                    "effect": f"This answer benched the reviewer: {after.bench_reason}.",
                }
            )
        return review

    def run_check(self, now: datetime) -> tuple[ReviewerHealth, list[GoldenResult]]:
        """Score every golden case and record the result (a fail benches the reviewer)."""
        cases = load_golden_set(self.golden_dir)
        results = [
            golden_result(c, self._ask(self.check_model, c.summary), self.config) for c in cases
        ]
        name = self.check_model.name
        health = self.health_store.update(
            lambda current: after_golden_check(
                current, results, self.config, name, self.prompt_version, now
            )
        )
        passed = sum(r.passed for r in results)
        logger.info(
            "reviewer check: model %s, prompt version %s, golden %d of %d passed (%.2f), "
            "result %s, state %s",
            name,
            self.prompt_version,
            passed,
            len(results),
            health.golden_pass_rate or 0.0,
            "pass" if health.last_check_passed else "fail",
            health.status,
        )
        for result in results:
            if not result.passed:
                logger.info("reviewer check: %s failed (%s)", result.name, result.status)
        return health, results

    def ensure_checked(self, now: datetime) -> ReviewerHealth:
        """Run the golden check once when this model and prompt were never checked."""
        health = self.health_store.load()
        if health.status == "benched" or is_usable(health, self.live.name, self.prompt_version):
            return health
        return self.run_check(now)[0]

    def enable(self) -> ReviewerHealth:
        name = self.live.name
        health = self.health_store.update(
            lambda current: enable(current, name, self.prompt_version)
        )
        logger.info("reviewer enabled by a person: model %s, prompt %s", name, self.prompt_version)
        return health

    def health(self) -> HealthReport:
        return health_report(
            self.health_store.load(),
            self.config.enabled,
            self.live.name,
            self.prompt_version,
        )


def make_case_reviewer(settings: Settings, data_dir: Path) -> CaseReviewerService:
    """The real reviewer: the local model, and the health file under data_dir."""
    config = settings.decision.members.case_reviewer
    return CaseReviewerService(
        settings,
        live=LocalCaseReviewer(settings.local_model, config.timeout_seconds),
        check=LocalCaseReviewer(settings.local_model, config.check_timeout_seconds),
        health=ReviewerHealthStore(data_dir / HEALTH_FILE),
    )


def decide_with_reviewer(
    case: ClaimCase,
    votes: Sequence[Vote],
    decide: DecideLane,
    settings: Settings,
    reviewer: CaseReviewerService | None,
    now: datetime,
) -> tuple[GuardedDecision, CaseReview | None]:
    """The council's decision, and the reviewer's review when it is switched on."""
    council = apply_reviewer(votes, None, decide, settings)
    if not settings.decision.members.case_reviewer.enabled:
        return council, None
    if reviewer is None:
        review = not_used(
            "skipped",
            "not_connected",
            settings.local_model.model,
            settings.local_model.reviewer_prompt_version,
            "No reviewer model was connected for this run.",
        )
        return council, review
    review = reviewer.review(case, votes, council.choice.lane, now)
    vote = review_vote(review)
    if vote is None:
        return council, review
    guarded = apply_reviewer(votes, vote, decide, settings)
    return guarded, review.model_copy(
        update={"changed_lane": guarded.changed_lane, "effect": guarded.effect}
    )
