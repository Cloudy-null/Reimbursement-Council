"""Payout math: network price cap, co-pay, benefit limits and VAT on the covered part.

All money is integer halalas. Rates go through apply_rate (Decimal, half up).
"""

from collections import defaultdict

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import ExtractionResult
from reimbursement_council.core.models.decision import PayoutResult
from reimbursement_council.core.models.reference import MemberHistory, Policy
from reimbursement_council.core.money import apply_rate


def _receipt_vat(extraction: ExtractionResult) -> int:
    """VAT the receipt charged: the VAT line, else total minus subtotal, else none."""
    vat = extraction.money("vat_total")
    if vat is not None:
        return vat
    total = extraction.money("total")
    subtotal = extraction.money("subtotal")
    if total is not None and subtotal is not None and total >= subtotal:
        return total - subtotal
    return 0


def calculate_payout(
    extraction: ExtractionResult,
    policy: Policy,
    history: MemberHistory,
    settings: Settings,
) -> PayoutResult | None:
    """What we pay for this receipt, with each cut shown. None when there are no line items."""
    if not extraction.line_items:
        return None
    tier = settings.policy.tiers.get(policy.tier)
    if tier is None:
        raise LookupError(f"policy {policy.policy_id} has tier {policy.tier}, not in policy.yaml")

    allowed_by_category: dict[str, int] = defaultdict(int)
    network_cap_cut = 0
    unmatched: list[str] = []
    for item in extraction.line_items:
        price = settings.prices.get(item.service_code or "")
        if price is None:
            unmatched.append(item.description)
            continue
        allowed = min(item.amount, price.network_price * item.quantity)
        network_cap_cut += item.amount - allowed
        allowed_by_category[price.category] += allowed

    copay = 0
    limit_cut = 0
    paid_before_vat = 0
    for category, allowed in allowed_by_category.items():
        category_copay = apply_rate(allowed, tier.copay_rate[category])
        after_copay = allowed - category_copay
        remaining = max(0, tier.limits_halalas[category] - history.limits_used.get(category, 0))
        paid = min(after_copay, remaining)
        copay += category_copay
        limit_cut += after_copay - paid
        paid_before_vat += paid

    receipt_vat = _receipt_vat(extraction)
    vat_paid = min(apply_rate(paid_before_vat, settings.policy.vat_rate), receipt_vat)
    requested = sum(item.amount for item in extraction.line_items) + receipt_vat
    is_partial = (
        network_cap_cut + limit_cut > settings.decision.partial_payout_tolerance_halalas
        or bool(unmatched)
    )
    return PayoutResult(
        requested=requested,
        network_cap_cut=network_cap_cut,
        copay=copay,
        limit_cut=limit_cut,
        vat_paid=vat_paid,
        calculated=paid_before_vat + vat_paid,
        unmatched_items=unmatched,
        is_partial=is_partial,
    )
