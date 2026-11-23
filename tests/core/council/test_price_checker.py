import pytest

from reimbursement_council.core.council import price_checker
from reimbursement_council.core.models.claim import LineItem
from reimbursement_council.core.models.decision import Vote
from tests.factories import make_case, make_extraction, make_item, repo_settings


def vote_for(items: list[LineItem]) -> Vote:
    return price_checker.vote(make_case(extraction=make_extraction([], items)), repo_settings())


@pytest.mark.parametrize(
    "unit_price, score", [(15000, 1.0), (10000, 1.0), (30000, 0.5), (45000, 0.0), (60000, 0.0)]
)
def test_price_ratio(unit_price: int, score: float) -> None:
    assert vote_for([make_item("CONS-GP", unit_price)]).score == pytest.approx(score)


def test_price_unknown_code_neutral() -> None:
    assert vote_for([make_item(None, 20000)]).score == 0.5


def test_price_amount_weighted() -> None:
    fair = make_item("CONS-GP", 15000)
    triple = make_item("MED-PARA", 13500, quantity=3)  # unit 4500, three times the 1500 price
    assert vote_for([fair, triple]).score == pytest.approx(15000 / 28500)


def test_price_worst_item_in_evidence() -> None:
    v = vote_for([make_item("CONS-GP", 15000), make_item("LAB-CBC", 24000)])
    assert v.evidence == ["LAB-CBC"] and v.request is None


def test_price_no_items_or_no_extraction() -> None:
    assert vote_for([]).score == 0.5
    assert price_checker.vote(make_case(extraction=None), repo_settings()).score == 0.5
