"""What the member is told before sending: the estimated payout and why it is lower. Pure.

Shown on the check page, so a sub-limit already used (for example eyeglass frames) is a plain
reason before submit, not a surprise after (source of the rules: Bupa Arabia claim FAQ).
"""

from reimbursement_council.config.message_models import LanguageMessages
from reimbursement_council.config.models import TierConfig
from reimbursement_council.core.models.decision import PayoutResult
from reimbursement_council.core.models.reference import MemberHistory
from reimbursement_council.core.money import format_sar


def estimate_lines(
    payout: PayoutResult | None,
    tier: TierConfig,
    history: MemberHistory,
    vat_on_receipt: int,
    language: LanguageMessages,
) -> list[str]:
    if payout is None:
        return []
    text = language.estimate
    lines = [
        text["total"].format(
            amount=format_sar(payout.calculated), requested=format_sar(payout.requested)
        )
    ]
    for key in payout.sub_limits_used:
        sub = tier.sub_limits.get(key)
        if sub is None or payout.sub_limit_cut == 0:
            continue
        before = max(0, sub.limit_halalas - history.limits_used.get(key, 0))
        lines.append(
            text["sub_limit"].format(
                cut=format_sar(payout.sub_limit_cut),
                benefit=text.get(f"benefit_{key}", key),
                left=format_sar(before),
                limit=format_sar(sub.limit_halalas),
            )
        )
    if payout.copay:
        cap = tier.copay_cap_halalas
        template = text["share_capped"] if cap is not None else text["share"]
        lines.append(template.format(share=format_sar(payout.copay), cap=format_sar(cap or 0)))
    if vat_on_receipt and payout.vat_paid == 0:
        lines.append(text["vat"].format(vat=format_sar(vat_on_receipt)))
    return lines
