"""The AI case reviewer at website startup: run the golden check in the background, so no
request ever waits for it, and give the web layer the reviewer's health (no HTML here)."""

import logging
import threading
from datetime import UTC, datetime

from reimbursement_council.core.models.case_review import HealthReport
from reimbursement_council.pipeline.case_review import CaseReviewerService
from reimbursement_council.web.context import WebContext

logger = logging.getLogger(__name__)


def _check(reviewer: CaseReviewerService) -> None:
    """Errors are only logged: a failed check leaves the reviewer unused, never the site down."""
    try:
        # Only when this model and prompt were never checked: a full golden run at every start
        # held the one model for minutes while members waited (core day 4b, e2e).
        reviewer.ensure_checked(datetime.now(UTC))
    except Exception:  # the council decides without the reviewer until a check passes
        logger.exception("reviewer startup check stopped early")


def start_reviewer_check(reviewer: CaseReviewerService) -> threading.Thread:
    thread = threading.Thread(target=_check, args=(reviewer,), name="reviewer-check", daemon=True)
    thread.start()
    return thread


def reviewer_health(ctx: WebContext) -> HealthReport | None:
    """The reviewer's health for a screen, or None when no reviewer is connected."""
    return None if ctx.case_reviewer is None else ctx.case_reviewer.health()


def reviewer_status_line(health: HealthReport | None, text: dict[str, str]) -> str:
    """One line for the numbers page: healthy or benched, last check, golden score, reason."""
    if health is None or health.state == "off":
        return text["reviewer_state_off"]
    parts = [text[f"reviewer_state_{health.state}"]]
    if health.last_check_at is not None:
        stamp = health.last_check_at.strftime("%Y-%m-%d %H:%M UTC")
        parts.append(f"{text['reviewer_last_check']} {stamp}")
    if health.golden_pass_rate is not None:
        parts.append(f"{text['reviewer_golden']} {health.golden_pass_rate:.2f}")
    if health.state == "benched" and health.bench_reason:
        parts.append(f"{text['reviewer_reason']}: {health.bench_reason}")
    return " | ".join(parts)
