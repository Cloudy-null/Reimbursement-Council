"""Reference data: members, policies, providers, history and the price list."""

from datetime import date
from typing import Literal, Self

from pydantic import Field, model_validator

from reimbursement_council.core.models.common import Halalas, Model, Score

NEUTRAL_TRUST = 0.5
"""Trust for a provider we have never seen. Neutral by definition, not a tunable."""


class Member(Model):
    member_id: str
    display_name: str
    date_joined: date
    policy_id: str


class Policy(Model):
    policy_id: str
    tier: str
    start_date: date
    end_date: date
    status: Literal["active", "inactive"]
    covered_people: list[str]


class Provider(Model):
    provider_id: str
    name: str
    vat_number: str | None
    city: str
    in_network: bool
    trust_score: Score

    @classmethod
    def unknown(cls, vat_number: str | None) -> "Provider":
        """A provider we cannot match. Neutral trust, treated as out of network."""
        return cls(
            provider_id="unknown",
            name="Unknown provider",
            vat_number=vat_number,
            city="",
            in_network=False,
            trust_score=NEUTRAL_TRUST,
        )


class MemberHistory(Model):
    member_id: str
    past_claims: int = Field(ge=0)
    past_claims_paid: int = Field(ge=0)
    limits_used: dict[str, Halalas]

    @model_validator(mode="after")
    def paid_within_past(self) -> Self:
        if self.past_claims_paid > self.past_claims:
            raise ValueError("past_claims_paid cannot be more than past_claims")
        return self


class PriceListItem(Model):
    service_code: str
    description: str
    network_price: Halalas
    category: str
    aliases: list[str] = Field(default_factory=list)


class ReferenceData(Model):
    members: list[Member]
    policies: list[Policy]
    providers: list[Provider]
    histories: list[MemberHistory]

    def member(self, member_id: str) -> Member:
        for member in self.members:
            if member.member_id == member_id:
                return member
        raise LookupError(f"unknown member_id: {member_id}")

    def policy(self, policy_id: str) -> Policy:
        for policy in self.policies:
            if policy.policy_id == policy_id:
                return policy
        raise LookupError(f"unknown policy_id: {policy_id}")

    def provider_by_vat(self, vat_number: str | None) -> Provider:
        if vat_number:
            for provider in self.providers:
                if provider.vat_number == vat_number:
                    return provider
        return Provider.unknown(vat_number)

    def history(self, member_id: str) -> MemberHistory:
        for history in self.histories:
            if history.member_id == member_id:
                return history
        return MemberHistory(member_id=member_id, past_claims=0, past_claims_paid=0, limits_used={})
