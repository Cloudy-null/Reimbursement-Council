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
    # Sub-limits (for example optical frames): what is left this policy year after the
    # member's usage so far (source: Bupa Arabia claim confirmation FAQ).
    sub_left = {
        key: max(0, sub.limit_halalas - history.limits_used.get(key, 0))
        for key, sub in tier.sub_limits.items()
    }
    sub_used: dict[str, int] = {}
    sub_limit_cut = 0
    for item in extraction.line_items:
        price = settings.prices.get(item.service_code or "")
        if price is None:
            unmatched.append(item.description)
            continue
        allowed = min(item.amount, price.network_price * item.quantity)
        network_cap_cut += item.amount - allowed
        for key, sub in tier.sub_limits.items():
            if price.service_code in sub.services:
                within = min(allowed, sub_left[key])
                sub_left[key] -= within
                sub_used[key] = sub_used.get(key, 0) + within
                sub_limit_cut += allowed - within
                allowed = within
        allowed_by_category[price.category] += allowed

    copay = 0
    limit_cut = 0
    paid_before_vat = 0
    # The member share is capped per claim (source: Bupa FAQ, "20% up to 100 SAR").
    share_left = tier.copay_cap_halalas
    for category, allowed in allowed_by_category.items():
        category_copay = apply_rate(allowed, tier.copay_rate[category])
        if share_left is not None:
            category_copay = min(category_copay, share_left)
            share_left -= category_copay
        after_copay = allowed - category_copay
        remaining = max(0, tier.limits_halalas[category] - history.limits_used.get(category, 0))
        paid = min(after_copay, remaining)
        copay += category_copay
        limit_cut += after_copay - paid
        paid_before_vat += paid

    receipt_vat = _receipt_vat(extraction)
    # Bupa does not cover VAT (source: Bupa FAQ); vat_covered in policy.yaml.
    vat_paid = (
        min(apply_rate(paid_before_vat, settings.policy.vat_rate), receipt_vat)
        if settings.policy.vat_covered
        else 0
    )
    requested = sum(item.amount for item in extraction.line_items) + receipt_vat
    is_partial = (
        network_cap_cut + limit_cut + sub_limit_cut
        > settings.decision.partial_payout_tolerance_halalas
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
        sub_limit_cut=sub_limit_cut,
        sub_limits_used=sub_used,
    )
