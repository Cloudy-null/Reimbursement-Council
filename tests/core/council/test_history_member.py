import pytest

from reimbursement_council.core.council import history_member
from reimbursement_council.core.models.reference import MemberHistory, Provider
from tests.factories import MEMBER_ID, make_case, repo_settings

TRUSTED_PROVIDER = Provider(
    provider_id="pr1",
    name="Al Noor Clinic",
    vat_number="300000000000003",
    city="Riyadh",
    in_network=True,
    trust_score=0.8,
)


def history(past: int, paid: int) -> MemberHistory:
    return MemberHistory(
        member_id=MEMBER_ID, past_claims=past, past_claims_paid=paid, limits_used={}
    )


def score(past: int, paid: int, provider: Provider) -> float:
    case = make_case(history=history(past, paid), provider=provider)
    return history_member.vote(case, repo_settings()).score


def test_history_new_member_unknown_provider_is_exactly_neutral() -> None:
    assert score(0, 0, Provider.unknown(None)) == 0.5


def test_history_trusted() -> None:
    assert score(5, 5, TRUSTED_PROVIDER) == pytest.approx(0.9)


def test_history_few_claims_neutral_part() -> None:
    assert score(2, 2, TRUSTED_PROVIDER) == pytest.approx(0.65)


def test_history_low() -> None:
    low_trust = TRUSTED_PROVIDER.model_copy(update={"trust_score": 0.5})
    assert score(5, 0, low_trust) == pytest.approx(0.25)


def test_history_never_requests() -> None:
    vote = history_member.vote(make_case(), repo_settings())
    assert vote.request is None and vote.member == "history_member"
