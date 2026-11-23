from reimbursement_council.config.models import Settings
from reimbursement_council.core.council.registry import run_council
from tests.factories import make_case, make_extraction, make_item, repo_settings, settings_with


def with_member(name: str, **changes: object) -> Settings:
    members = repo_settings().decision.members
    member = getattr(members, name).model_copy(update=changes)
    return settings_with(members=members.model_copy(update={name: member}))


def test_council_order_and_weights() -> None:
    case = make_case(extraction=make_extraction([], [make_item("CONS-GP", 15000)]))
    votes = run_council(case, with_member("price_checker", weight=2.0))
    assert [v.member for v in votes] == [
        "document_checker",
        "coverage_checker",
        "price_checker",
        "history_member",
    ]
    assert [v.weight for v in votes] == [1.0, 1.0, 2.0, 1.0]


def test_council_skips_disabled() -> None:
    votes = run_council(make_case(), with_member("history_member", enabled=False))
    assert [v.member for v in votes] == ["document_checker", "coverage_checker", "price_checker"]
