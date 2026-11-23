from reimbursement_council.core.council import coverage_checker
from reimbursement_council.core.models.claim import LineItem
from reimbursement_council.core.models.decision import PayoutResult, Vote
from reimbursement_council.core.payout import calculate_payout
from tests.factories import make_case, make_extraction, make_item, make_policy, repo_settings


def vote_for(items: list[LineItem]) -> Vote:
    extraction = make_extraction([], items)
    case = make_case(extraction=extraction)
    payout: PayoutResult | None = calculate_payout(
        extraction, make_policy(), case.history, repo_settings()
    )
    case = case.model_copy(update={"payout": payout})
    return coverage_checker.vote(case, repo_settings())


def test_coverage_all_matched() -> None:
    v = vote_for([make_item("CONS-GP", 15000), make_item("LAB-CBC", 8000)])
    assert v.score == 1.0 and v.request is None


def test_coverage_half_unmatched() -> None:
    v = vote_for([make_item("CONS-GP", 15000), make_item(None, 15000, description="Physio")])
    assert v.score == 0.5
    assert v.request is None
    assert "Physio" in v.evidence


def test_coverage_no_items_asks_itemized() -> None:
    v = vote_for([])
    assert v.score == 0.3
    assert (v.request_kind, v.request_field) == ("add_document", "itemized_invoice")


def test_coverage_no_extraction() -> None:
    v = coverage_checker.vote(make_case(extraction=None), repo_settings())
    assert v.score == 0.0 and v.request is None


def test_coverage_vote_is_named() -> None:
    assert vote_for([make_item("CONS-GP", 15000)]).member == "coverage_checker"
