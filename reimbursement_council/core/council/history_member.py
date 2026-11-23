"""History member: how much past claims and provider trust support this claim.

Guardrails: a member with little or no history gets the neutral part 0.5, never a low one.
Tenure is not used. This member never asks for anything, and it cannot reject a claim:
only hard rules reject.
"""

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.case import ClaimCase
from reimbursement_council.core.models.decision import Vote

MEMBER = "history_member"
NEUTRAL = 0.5


def vote(case: ClaimCase, settings: Settings) -> Vote:
    config = settings.decision.members.history_member
    history = case.history
    if history.past_claims >= config.min_past_claims:
        member_part = history.past_claims_paid / history.past_claims
        member_reason = f"{history.past_claims_paid} of {history.past_claims} past claims paid"
    else:
        member_part = NEUTRAL
        member_reason = f"only {history.past_claims} past claims, neutral"
    score = (member_part + case.provider.trust_score) / 2
    reason = f"History {member_reason}; provider trust {case.provider.trust_score:.2f}."
    return Vote(member=MEMBER, score=score, reason=reason, evidence=["history", "provider"])
