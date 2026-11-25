"""Adding a new member: checking the form and building the member, policy and history."""

from collections.abc import Callable
from datetime import date

import pytest

from reimbursement_council.core.models.reference import ReferenceData
from reimbursement_council.core.new_member import (
    NewMember,
    NewMemberError,
    NewMemberForm,
    benefit_keys,
    build_new_member,
    check_new_member,
    with_new_members,
)
from tests.factories import repo_settings

TODAY = date(2026, 11, 25)


def ids() -> Callable[[], str]:
    counter = iter(range(1, 100))
    return lambda: f"00000000-0000-4000-8000-0000000009{next(counter):02d}"


def form(**changes: object) -> NewMemberForm:
    values: dict[str, object] = {
        "name": "Sara Ahmed",
        "name_ar": "سارة أحمد",
        "tier": "silver",
        "dependants": (),
        "used": {},
    }
    values.update(changes)
    return NewMemberForm(**values)  # type: ignore[arg-type]


def build(**changes: object) -> NewMember:
    return build_new_member(form(**changes), repo_settings().policy, TODAY, ids())


def test_benefit_keys_come_from_the_tier_limits() -> None:
    keys = benefit_keys(repo_settings().policy)
    assert set(repo_settings().policy.tiers["silver"].limits_halalas) <= set(keys)
    assert len(keys) == len(set(keys))


def test_good_input_builds_member_policy_and_history() -> None:
    added = build(
        dependants=("Omar Ahmed",), used={"dental": "600", "lab": "12.50", "pharmacy": ""}
    )
    main, child = added.members
    assert main.display_name == "Sara Ahmed"
    assert main.name_ar == "سارة أحمد"
    assert main.date_joined == TODAY
    assert child.display_name == "Omar Ahmed"
    assert child.name_ar is None
    assert main.policy_id == child.policy_id == added.policy.policy_id
    assert added.policy.tier == "silver"
    assert added.policy.status == "active"
    assert added.policy.start_date == date(2025, 11, 25)
    assert added.policy.end_date == date(2027, 11, 25)
    assert added.policy.covered_people == [main.member_id, child.member_id]
    history = added.histories[0]
    assert history.member_id == main.member_id
    assert history.past_claims == 0
    assert history.past_claims_paid == 0
    assert history.limits_used == {"dental": 60000, "lab": 1250}
    assert added.histories[1].limits_used == {}
    assert len({main.member_id, child.member_id, added.policy.policy_id}) == 3


def test_names_are_trimmed_and_arabic_name_is_optional() -> None:
    added = build(name="  Sara Ahmed ", name_ar="  ")
    assert added.members[0].display_name == "Sara Ahmed"
    assert added.members[0].name_ar is None


def test_leap_day_policy_dates() -> None:
    added = build_new_member(form(), repo_settings().policy, date(2028, 2, 29), ids())
    assert added.policy.start_date == date(2027, 2, 28)
    assert added.policy.end_date == date(2029, 2, 28)


@pytest.mark.parametrize(
    ("changes", "field", "code"),
    [
        ({"name": ""}, "name", "member_name_missing"),
        ({"name": "   "}, "name", "member_name_missing"),
        ({"name": "S"}, "name", "member_name_length"),
        ({"name": "S" * 81}, "name", "member_name_length"),
        ({"name": "Sara 2"}, "name", "member_name_digits"),
        ({"name": "سارة ٢"}, "name", "member_name_digits"),
        ({"name_ar": "س"}, "name_ar", "member_name_length"),
        ({"name_ar": "سارة 3"}, "name_ar", "member_name_digits"),
        ({"tier": "platinum"}, "tier", "member_tier_unknown"),
        ({"tier": ""}, "tier", "member_tier_unknown"),
        ({"dependants": ("A",)}, "dependants", "member_name_length"),
        ({"dependants": ("Omar 1",)}, "dependants", "member_name_digits"),
        ({"dependants": tuple(f"Child {c}" for c in "abcdef")}, "dependants", "member_too_many"),
        ({"used": {"dental": "-5"}}, "used_dental", "member_amount_bad"),
        ({"used": {"dental": "abc"}}, "used_dental", "member_amount_bad"),
        ({"used": {"dental": "1.234"}}, "used_dental", "member_amount_bad"),
        ({"used": {"spa": "10"}}, "used_spa", "member_benefit_unknown"),
    ],
)
def test_each_bad_input_is_refused(changes: dict[str, object], field: str, code: str) -> None:
    errors = check_new_member(form(**changes), repo_settings().policy)
    assert errors == {field: code}
    with pytest.raises(NewMemberError) as raised:
        build(**changes)
    assert raised.value.errors == {field: code}


def test_five_dependants_is_allowed() -> None:
    added = build(dependants=tuple(f"Child {c}" for c in "abcde"))
    assert len(added.members) == 6


def test_blank_dependant_lines_are_ignored() -> None:
    added = build(dependants=("", "  ", "Omar Ahmed"))
    assert [m.display_name for m in added.members] == ["Sara Ahmed", "Omar Ahmed"]


def test_with_new_members_adds_people_to_the_reference() -> None:
    base = ReferenceData(members=[], policies=[], providers=[], histories=[])
    added = build(dependants=("Omar Ahmed",), used={"dental": "600"})
    merged = with_new_members(base, [added])
    main = added.members[0]
    assert merged.member(main.member_id) == main
    assert merged.policy(main.policy_id) == added.policy
    assert merged.history(main.member_id).limits_used == {"dental": 60000}
    assert len(merged.members) == 2


def test_with_new_members_never_replaces_a_seeded_person() -> None:
    added = build()
    base = with_new_members(
        ReferenceData(members=[], policies=[], providers=[], histories=[]), [added]
    )
    again = with_new_members(base, [added])
    assert again == base
