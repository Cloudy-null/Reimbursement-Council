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
        reviewer.run_check(datetime.now(UTC))
    except Exception:  # the council decides without the reviewer until a check passes
        logger.exception("reviewer startup check stopped early")


def start_reviewer_check(reviewer: CaseReviewerService) -> threading.Thread:
    thread = threading.Thread(target=_check, args=(reviewer,), name="reviewer-check", daemon=True)
    thread.start()
    return thread


def reviewer_health(ctx: WebContext) -> HealthReport | None:
    """The reviewer's health for a screen, or None when no reviewer is connected."""
    return None if ctx.case_reviewer is None else ctx.case_reviewer.health()
