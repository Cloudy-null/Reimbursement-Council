import pytest

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import LineItem
from reimbursement_council.core.models.decision import PayoutResult
from reimbursement_council.core.models.reference import MemberHistory
from reimbursement_council.core.payout import calculate_payout
from tests.factories import (
    MEMBER_ID,
    make_extraction,
    make_field,
    make_item,
    make_policy,
    repo_settings,
)

EMPTY_HISTORY = MemberHistory(
    member_id=MEMBER_ID, past_claims=0, past_claims_paid=0, limits_used={}
)


def payout(
    items: list[LineItem],
    vat_total: str | None,
    history: MemberHistory = EMPTY_HISTORY,
    vat_covered: bool = False,
) -> PayoutResult | None:
    fields = [make_field("vat_total", vat_total)] if vat_total is not None else []
    settings = repo_settings()
    policy = settings.policy.model_copy(update={"vat_covered": vat_covered})
    settings = settings.model_copy(update={"policy": policy})
    return calculate_payout(make_extraction(fields, items), make_policy(), history, settings)


def must(result: PayoutResult | None) -> PayoutResult:
    assert result is not None
    return result


def vat_settings() -> Settings:
    settings = repo_settings()
    return settings.model_copy(
        update={"policy": settings.policy.model_copy(update={"vat_covered": True})}
    )


def vat_payout(
    items: list[LineItem], vat_total: str | None, history: MemberHistory = EMPTY_HISTORY
) -> PayoutResult | None:
    """The tests below were written when VAT was paid; they now test vat_covered: true."""
    return payout(items, vat_total, history, vat_covered=True)


def test_clean_consultation() -> None:
    p = must(vat_payout([make_item("CONS-GP", 15000)], "2250"))
    assert (p.network_cap_cut, p.copay, p.limit_cut, p.vat_paid) == (0, 1500, 0, 2025)
    assert (p.requested, p.calculated, p.is_partial) == (17250, 15525, False)
    assert p.unmatched_items == []


def test_network_cap() -> None:
    p = must(vat_payout([make_item("CONS-GP", 40000)], "6000"))
    assert (p.network_cap_cut, p.calculated, p.is_partial) == (25000, 15525, True)
    assert p.requested == 46000


def test_limit_cut() -> None:
    used = MemberHistory(
        member_id=MEMBER_ID, past_claims=1, past_claims_paid=1, limits_used={"outpatient": 1495000}
    )
    p = must(vat_payout([make_item("CONS-GP", 15000)], "2250", used))
    assert (p.limit_cut, p.vat_paid, p.calculated, p.is_partial) == (8500, 750, 5750, True)


def test_limit_fully_used() -> None:
    used = MemberHistory(
        member_id=MEMBER_ID, past_claims=1, past_claims_paid=1, limits_used={"outpatient": 1500000}
    )
    p = must(vat_payout([make_item("CONS-GP", 15000)], "2250", used))
    assert (p.calculated, p.vat_paid, p.limit_cut, p.is_partial) == (0, 0, 13500, True)


def test_unmatched_item() -> None:  # Review Focus 4
    p = must(vat_payout([make_item(None, 20000, description="Physio session")], "3000"))
    assert p.unmatched_items == ["Physio session"]
    assert (p.requested, p.calculated, p.is_partial) == (23000, 0, True)


def test_unknown_code_counts_as_unmatched() -> None:
    p = must(vat_payout([make_item("NOT-A-CODE", 20000, description="Mystery")], None))
    assert p.unmatched_items == ["Mystery"]


def test_no_line_items_gives_none() -> None:
    assert vat_payout([], "2250") is None


def test_no_vat_receipt() -> None:
    p = must(vat_payout([make_item("CONS-GP", 15000)], "0"))
    assert (p.vat_paid, p.requested, p.calculated) == (0, 15000, 13500)
    assert must(vat_payout([make_item("CONS-GP", 15000)], None)).vat_paid == 0


def test_quantity() -> None:
    p = must(vat_payout([make_item("MED-PARA", 4500, quantity=3)], "0"))
    assert (p.network_cap_cut, p.copay, p.calculated) == (0, 900, 3600)


def test_two_categories() -> None:
    p = must(vat_payout([make_item("CONS-GP", 15000), make_item("LAB-CBC", 8000)], "3450"))
    # outpatient 15000 - 1500 co-pay, lab 8000 with no co-pay, VAT on the paid 21500
    assert (p.copay, p.vat_paid, p.calculated) == (1500, 3225, 24725)


def test_unknown_tier_names_it() -> None:
    policy = make_policy().model_copy(update={"tier": "platinum"})
    extraction = make_extraction([], [make_item("CONS-GP", 15000)])
    with pytest.raises(LookupError, match="platinum"):
        calculate_payout(extraction, policy, EMPTY_HISTORY, repo_settings())


def test_vat_derived_when_unreadable() -> None:  # final review: VAT underpaid
    fields = [make_field("subtotal", "15000"), make_field("total", "17250")]
    p = must(
        calculate_payout(
            make_extraction(fields, [make_item("CONS-GP", 15000)]),
            make_policy(),
            EMPTY_HISTORY,
            vat_settings(),
        )
    )
    assert (p.vat_paid, p.requested, p.calculated) == (2025, 17250, 15525)


def test_vat_paid_never_above_receipt_vat() -> None:  # final review: VAT overpaid
    p = must(vat_payout([make_item("LAB-CBC", 8000)], "100"))
    assert (p.vat_paid, p.requested, p.calculated) == (100, 8100, 8100)


def test_real_case_frames_over_the_sub_limit_and_share_capped() -> None:
    """The real optical claim (core day 4b): frames 1,600 + lenses 150, 600 of the 1,000 SAR
    frame sub-limit already used. Bupa paid 450: 1,750 - 1,200 over the sub-limit - 100 share."""
    used = MemberHistory(
        member_id=MEMBER_ID,
        past_claims=1,
        past_claims_paid=1,
        limits_used={"optical_frames": 60000},
    )
    p = must(payout([make_item("OPT-FRAME", 160000), make_item("OPT-LENS", 15000)], "0", used))
    assert p.sub_limit_cut == 120000
    assert p.copay == 10000  # 20% of 550 is 110, capped at 100
    assert p.calculated == 45000
    assert p.sub_limits_used == {"optical_frames": 40000}
    assert p.is_partial


def test_vat_is_not_paid() -> None:
    p = must(payout([make_item("CONS-GP", 15000)], "2250"))
    assert p.vat_paid == 0
    assert p.requested == 17250  # what the member paid, VAT included


def test_member_share_is_capped_per_claim() -> None:
    p = must(payout([make_item("OPT-FRAME", 100000)], "0"))
    assert p.copay == 10000  # 20% of 1,000 is 200, capped at 100
