"""Run every enabled council member in config order and stamp each vote with its weight."""

import logging
from collections.abc import Callable

from reimbursement_council.config.models import Settings
from reimbursement_council.core.council import (
    coverage_checker,
    document_checker,
    history_member,
    price_checker,
)
from reimbursement_council.core.models.case import ClaimCase
from reimbursement_council.core.models.common import MemberName
from reimbursement_council.core.models.decision import Vote

logger = logging.getLogger(__name__)

MemberVote = Callable[[ClaimCase, Settings], Vote]

BUILT_MEMBERS: dict[MemberName, MemberVote] = {
    "document_checker": document_checker.vote,
    "coverage_checker": coverage_checker.vote,
    "price_checker": price_checker.vote,
    "history_member": history_member.vote,
}


def run_council(case: ClaimCase, settings: Settings) -> list[Vote]:
    votes: list[Vote] = []
    for name, config in settings.decision.members.in_order():
        if not config.enabled:
            continue
        member_vote = BUILT_MEMBERS.get(name)
        if member_vote is None:
            raise ValueError(f"council member {name} is enabled but not built")
        votes.append(member_vote(case, settings).model_copy(update={"weight": config.weight}))
    logger.info(
        "claim %s: %s",
        case.claim.claim_id,
        ", ".join(f"{v.member} {v.score:.2f}" for v in votes),
    )
    return votes
