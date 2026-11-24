"""Member message in Arabic and English, from the fixed templates in config/messages.yaml.

No model writes member text: only templates filled with values, so wording stays consistent.
"""

from collections.abc import Sequence

from reimbursement_council.config.models import LanguageMessages, Settings
from reimbursement_council.core.decision.lanes import LaneChoice
from reimbursement_council.core.models.decision import (
    MemberMessage,
    PayoutResult,
    RuleResult,
)
from reimbursement_council.core.money import format_sar


def _render(
    language: LanguageMessages,
    choice: LaneChoice,
    rule_results: Sequence[RuleResult],
    payout: PayoutResult | None,
    settings: Settings,
) -> str:
    lanes = language.lanes
    if choice.lane == "auto_approve":
        if payout is None:
            raise ValueError("an approved claim needs a payout")
        amount = format_sar(payout.calculated)
        if choice.outcome == "partial":
            return lanes.approved_partial.format(
                amount=amount, requested=format_sar(payout.requested)
            )
        return lanes.approved.format(amount=amount)
    if choice.lane == "auto_reject":
        failed = next((result for result in rule_results if result.outcome == "fail"), None)
        if failed is None:
            raise ValueError("a rejected claim needs a failed hard rule")
        template: str = getattr(language.rules, failed.rule)
        reason = template.format(claim_window_days=settings.policy.claim_window_days)
        return lanes.rejected.format(reason=reason)
    if choice.lane == "self_fix":
        if choice.request is None:
            raise ValueError("a self-fix claim needs a request")
        field = choice.request.field
        if choice.request.kind == "add_document" and field in language.documents:
            documents = language.documents[field]
            request = language.requests.missing_document.format(documents=documents)
        else:
            label = language.fields.get(field, field)
            request_template: str = getattr(language.requests, choice.request.kind)
            request = request_template.format(field=label)
        return lanes.self_fix.format(request=request)
    return lanes.human_review


def build_member_message(
    choice: LaneChoice,
    rule_results: Sequence[RuleResult],
    payout: PayoutResult | None,
    settings: Settings,
) -> MemberMessage:
    messages = settings.messages
    return MemberMessage(
        en=_render(messages.en, choice, rule_results, payout, settings),
        ar=_render(messages.ar, choice, rule_results, payout, settings),
    )
