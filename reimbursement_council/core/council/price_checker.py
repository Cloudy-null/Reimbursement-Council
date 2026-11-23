"""Price checker: how normal the prices are against the reference price list.

At or under the network price scores 1.0. The score falls in a straight line to 0.0 at
zero_score_ratio times the network price. Unknown items score unknown_item_score.
"""

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.case import ClaimCase
from reimbursement_council.core.models.decision import Vote

MEMBER = "price_checker"


def _item_score(unit_price: int, network_price: int, zero_score_ratio: float) -> float:
    if network_price == 0:
        return 1.0 if unit_price == 0 else 0.0
    ratio = unit_price / network_price
    if ratio <= 1.0:
        return 1.0
    return max(0.0, 1.0 - (ratio - 1.0) / (zero_score_ratio - 1.0))


def vote(case: ClaimCase, settings: Settings) -> Vote:
    config = settings.decision.members.price_checker
    items = [] if case.extraction is None else case.extraction.line_items
    total = sum(item.amount for item in items)
    if not items or total == 0:
        return Vote(
            member=MEMBER,
            score=config.unknown_item_score,
            reason="No priced line items to compare.",
            evidence=[],
        )

    weighted = 0.0
    high: list[tuple[float, str]] = []
    for item in items:
        price = settings.prices.get(item.service_code or "")
        if price is None:
            item_score = config.unknown_item_score
        else:
            item_score = _item_score(item.unit_price, price.network_price, config.zero_score_ratio)
            if item_score < 1.0:
                high.append((item_score, price.service_code))
        weighted += item_score * item.amount
    score = weighted / total
    high.sort()
    reason = (
        f"Prices score {score:.2f}; highest against the list: {high[0][1]}."
        if high
        else f"Prices score {score:.2f}; no item is above the network price."
    )
    return Vote(member=MEMBER, score=score, reason=reason, evidence=[code for _, code in high])
