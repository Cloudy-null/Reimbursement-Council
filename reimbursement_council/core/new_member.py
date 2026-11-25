"""Adding a new member by hand, so a real person can be tested: check the form, then build the
member, the people on the policy, the policy and the benefit usage so far. Pure, no I/O.

Error codes are website text keys (web/i18n), so the website and the CLI say the same thing.
"""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date

from reimbursement_council.config.models import PolicyConfig
from reimbursement_council.core.models.common import Model
from reimbursement_council.core.models.reference import (
    Member,
    MemberHistory,
    Policy,
    ReferenceData,
)
from reimbursement_council.core.money import parse_sar_to_halalas

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 80
MAX_DEPENDANTS = 5
"""Form rules, not tunable policy: they only keep typed input sane."""


@dataclass(frozen=True)
class NewMemberForm:
    """What was typed, as text. Money is SAR text such as "600" or "600.00"."""

    name: str
    name_ar: str = ""
    tier: str = ""
    dependants: tuple[str, ...] = ()
    used: Mapping[str, str] = field(default_factory=dict)


class NewMember(Model):
    """One added policy: members[0] is the member, the rest are dependants."""

    members: list[Member]
    policy: Policy
    histories: list[MemberHistory]


class NewMemberError(ValueError):
    def __init__(self, errors: Mapping[str, str]) -> None:
        super().__init__(f"the new member is not valid: {dict(errors)}")
        self.errors = dict(errors)


def _sub_limit_keys(section: object) -> list[str]:
    """Keys under a sub_limits section, when the policy config has one."""
    sub_limits = getattr(section, "sub_limits", None)
    return [str(key) for key in sub_limits] if isinstance(sub_limits, Mapping) else []


def benefit_keys(policy: PolicyConfig) -> tuple[str, ...]:
    """Every benefit a usage can be given for: categories in any tier's limits, then any
    sub-limit keys (policy-wide or per tier). Config order, no repeats."""
    keys: list[str] = []
    for tier in policy.tiers.values():
        keys.extend(tier.limits_halalas)
        keys.extend(_sub_limit_keys(tier))
    keys.extend(_sub_limit_keys(policy))
    return tuple(dict.fromkeys(keys))


def _name_error(name: str) -> str | None:
    if not name:
        return "member_name_missing"
    if not NAME_MIN_LENGTH <= len(name) <= NAME_MAX_LENGTH:
        return "member_name_length"
    if any(character.isdigit() for character in name):
        return "member_name_digits"
    return None


def _dependants(form: NewMemberForm) -> list[str]:
    return [name.strip() for name in form.dependants if name.strip()]


def check_new_member(form: NewMemberForm, policy: PolicyConfig) -> dict[str, str]:
    """Field name to error code. Empty when the form is good."""
    errors: dict[str, str] = {}
    if (error := _name_error(form.name.strip())) is not None:
        errors["name"] = error
    if form.name_ar.strip() and (error := _name_error(form.name_ar.strip())) is not None:
        errors["name_ar"] = error
    if form.tier not in policy.tiers:
        errors["tier"] = "member_tier_unknown"
    dependants = _dependants(form)
    if len(dependants) > MAX_DEPENDANTS:
        errors["dependants"] = "member_too_many"
    else:
        for name in dependants:
            if (error := _name_error(name)) is not None:
                errors["dependants"] = error
                break
    known = benefit_keys(policy)
    for key, text in form.used.items():
        if key not in known:
            errors[f"used_{key}"] = "member_benefit_unknown"
        elif text.strip() and parse_sar_to_halalas(text) is None:
            errors[f"used_{key}"] = "member_amount_bad"
    return errors


def _years_from(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 29 February in a year that has none
        return day.replace(year=day.year + years, day=28)


def _used_halalas(used: Mapping[str, str]) -> dict[str, int]:
    amounts = {key: parse_sar_to_halalas(text) for key, text in used.items() if text.strip()}
    return {key: amount for key, amount in amounts.items() if amount}


def build_new_member(
    form: NewMemberForm, policy: PolicyConfig, today: date, new_id: Callable[[], str]
) -> NewMember:
    """The member, dependants, an active policy (one year back to one year ahead) and a
    history with no past claims. Raises NewMemberError with every problem found."""
    errors = check_new_member(form, policy)
    if errors:
        raise NewMemberError(errors)
    policy_id = new_id()
    names = [(form.name.strip(), form.name_ar.strip() or None)]
    names += [(name, None) for name in _dependants(form)]
    members = [
        Member(
            member_id=new_id(),
            display_name=name,
            name_ar=name_ar,
            date_joined=today,
            policy_id=policy_id,
        )
        for name, name_ar in names
    ]
    used = _used_halalas(form.used)
    return NewMember(
        members=members,
        policy=Policy(
            policy_id=policy_id,
            tier=form.tier,
            start_date=_years_from(today, -1),
            end_date=_years_from(today, 1),
            status="active",
            covered_people=[member.member_id for member in members],
        ),
        histories=[
            MemberHistory(
                member_id=member.member_id,
                past_claims=0,
                past_claims_paid=0,
                limits_used=used if index == 0 else {},
            )
            for index, member in enumerate(members)
        ],
    )


def with_new_members(base: ReferenceData, added: Iterable[NewMember]) -> ReferenceData:
    """The reference plus added members. A person or policy already there is never replaced."""
    member_ids = {member.member_id for member in base.members}
    policy_ids = {policy.policy_id for policy in base.policies}
    history_ids = {history.member_id for history in base.histories}
    members, policies, histories = list(base.members), list(base.policies), list(base.histories)
    for new in added:
        if new.policy.policy_id in policy_ids:
            continue
        policy_ids.add(new.policy.policy_id)
        policies.append(new.policy)
        for member in new.members:
            if member.member_id not in member_ids:
                member_ids.add(member.member_id)
                members.append(member)
        for history in new.histories:
            if history.member_id not in history_ids:
                history_ids.add(history.member_id)
                histories.append(history)
    return base.model_copy(
        update={"members": members, "policies": policies, "histories": histories}
    )
