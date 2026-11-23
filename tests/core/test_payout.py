import pytest

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
    items: list[LineItem], vat_total: str | None, history: MemberHistory = EMPTY_HISTORY
) -> PayoutResult | None:
    fields = [make_field("vat_total", vat_total)] if vat_total is not None else []
    return calculate_payout(make_extraction(fields, items), make_policy(), history, repo_settings())


def must(result: PayoutResult | None) -> PayoutResult:
    assert result is not None
    return result


def test_clean_consultation() -> None:
    p = must(payout([make_item("CONS-GP", 15000)], "2250"))
    assert (p.network_cap_cut, p.copay, p.limit_cut, p.vat_paid) == (0, 1500, 0, 2025)
    assert (p.requested, p.calculated, p.is_partial) == (17250, 15525, False)
    assert p.unmatched_items == []


def test_network_cap() -> None:
    p = must(payout([make_item("CONS-GP", 40000)], "6000"))
    assert (p.network_cap_cut, p.calculated, p.is_partial) == (25000, 15525, True)
    assert p.requested == 46000


def test_limit_cut() -> None:
    used = MemberHistory(
        member_id=MEMBER_ID, past_claims=1, past_claims_paid=1, limits_used={"outpatient": 1495000}
    )
    p = must(payout([make_item("CONS-GP", 15000)], "2250", used))
    assert (p.limit_cut, p.vat_paid, p.calculated, p.is_partial) == (8500, 750, 5750, True)


def test_limit_fully_used() -> None:
    used = MemberHistory(
        member_id=MEMBER_ID, past_claims=1, past_claims_paid=1, limits_used={"outpatient": 1500000}
    )
    p = must(payout([make_item("CONS-GP", 15000)], "2250", used))
    assert (p.calculated, p.vat_paid, p.limit_cut, p.is_partial) == (0, 0, 13500, True)


def test_unmatched_item() -> None:  # Review Focus 4
    p = must(payout([make_item(None, 20000, description="Physio session")], "3000"))
    assert p.unmatched_items == ["Physio session"]
    assert (p.requested, p.calculated, p.is_partial) == (23000, 0, True)


def test_unknown_code_counts_as_unmatched() -> None:
    p = must(payout([make_item("NOT-A-CODE", 20000, description="Mystery")], None))
    assert p.unmatched_items == ["Mystery"]


def test_no_line_items_gives_none() -> None:
    assert payout([], "2250") is None


def test_no_vat_receipt() -> None:
    p = must(payout([make_item("CONS-GP", 15000)], "0"))
    assert (p.vat_paid, p.requested, p.calculated) == (0, 15000, 13500)
    assert must(payout([make_item("CONS-GP", 15000)], None)).vat_paid == 0


def test_quantity() -> None:
    p = must(payout([make_item("MED-PARA", 4500, quantity=3)], "0"))
    assert (p.network_cap_cut, p.copay, p.calculated) == (0, 900, 3600)


def test_two_categories() -> None:
    p = must(payout([make_item("CONS-GP", 15000), make_item("LAB-CBC", 8000)], "3450"))
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
            repo_settings(),
        )
    )
    assert (p.vat_paid, p.requested, p.calculated) == (2025, 17250, 15525)


def test_vat_paid_never_above_receipt_vat() -> None:  # final review: VAT overpaid
    p = must(payout([make_item("LAB-CBC", 8000)], "100"))
    assert (p.vat_paid, p.requested, p.calculated) == (100, 8100, 8100)
