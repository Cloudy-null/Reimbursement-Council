from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from reimbursement_council.core.models.claim import Claim, Document, LineItem
from reimbursement_council.core.models.decision import Decision, MemberMessage, Vote
from reimbursement_council.core.models.reference import (
    Member,
    MemberHistory,
    Policy,
    Provider,
    ReferenceData,
)
from tests.factories import make_extraction, make_field

NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)


def make_document() -> Document:
    return Document(
        document_id="d1",
        claim_id="c1",
        kind="receipt",
        file_path="receipt.png",
        image_hash=None,
        uploaded_at=NOW,
    )


def make_claim(submitted_at: datetime = NOW) -> Claim:
    return Claim(
        claim_id="c1",
        member_id="m1",
        patient_member_id="m1",
        policy_id="p1",
        submitted_at=submitted_at,
        status="submitted",
        documents=[make_document()],
        retries_used=0,
    )


def make_decision(lane: str = "auto_approve") -> Decision:
    return Decision(
        claim_id="c1",
        decided_at=NOW,
        config_version="abc123def456",
        combined_score=0.9,
        p_good=0.9,
        disagreement=0.1,
        payout_requested=17250,
        payout_calculated=15525,
        expected_loss=1553,
        reviewer_time_value=2500,
        lane=lane,  # type: ignore[arg-type]
        lane_reason="test",
        outcome="complete",
        self_fix_request=None,
        member_message=MemberMessage(en="ok", ar="ok"),
        votes=[],
        rule_results=[],
        check_results=[],
    )


def test_score_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        make_field("total", "100", confidence=1.5)


def test_money_never_float() -> None:
    with pytest.raises(ValidationError):
        LineItem(
            description="x",
            service_code=None,
            quantity=1,
            unit_price=10.5,  # type: ignore[arg-type]
            amount=10,
            confidence=0.9,
        )


def test_money_never_negative() -> None:
    with pytest.raises(ValidationError):
        LineItem(
            description="x", service_code=None, quantity=1, unit_price=-1, amount=10, confidence=0.9
        )


def test_naive_submitted_at_rejected() -> None:
    with pytest.raises(ValidationError):
        make_claim(submitted_at=datetime(2026, 11, 20, 9, 0))


def test_valid_claim_builds() -> None:
    assert make_claim().documents[0].kind == "receipt"


def test_unknown_lane_rejected() -> None:
    assert make_decision().lane == "auto_approve"
    with pytest.raises(ValidationError):
        make_decision(lane="maybe")


def test_vote_request_all_or_nothing() -> None:
    Vote(member="document_checker", score=0.5, reason="r", evidence=[])
    Vote(
        member="document_checker",
        score=0.5,
        reason="r",
        evidence=[],
        request="Please retake the photo.",
        request_kind="retake_photo",
        request_field="total",
    )
    with pytest.raises(ValidationError):
        Vote(member="document_checker", score=0.5, reason="r", evidence=[], request="text only")


def test_vote_weight_defaults_to_one() -> None:
    assert Vote(member="price_checker", score=1.0, reason="r", evidence=[]).weight == 1.0


def test_extra_keys_rejected() -> None:
    with pytest.raises(ValidationError):
        Member(
            member_id="m1",
            display_name="Sara",
            date_joined=date(2024, 1, 1),
            policy_id="p1",
            nationality="x",  # type: ignore[call-arg]
        )


def test_extraction_accessors() -> None:
    ex = make_extraction(
        [
            make_field("total", "17250", 0.6),
            make_field("total", "17000", 0.95),
            make_field("treatment_date", "2026-11-15"),
            make_field("invoice_timestamp", "bad date"),
        ]
    )
    best = ex.best("total")
    assert best is not None and best.value == "17000"
    assert len(ex.all_named("total")) == 2
    assert ex.money("total") == 17000
    assert ex.day("treatment_date") == date(2026, 11, 15)
    assert ex.money("vat_total") is None
    assert ex.day("invoice_timestamp") is None


def test_unknown_provider_is_neutral() -> None:
    p = Provider.unknown("300000000000003")
    assert p.trust_score == 0.5 and p.in_network is False and p.provider_id == "unknown"
    assert p.vat_number == "300000000000003"


def test_history_paid_cannot_exceed_past() -> None:
    with pytest.raises(ValidationError):
        MemberHistory(member_id="m1", past_claims=2, past_claims_paid=3, limits_used={})


def build_reference() -> ReferenceData:
    return ReferenceData(
        members=[
            Member(
                member_id="m1", display_name="Sara", date_joined=date(2024, 1, 1), policy_id="p1"
            )
        ],
        policies=[
            Policy(
                policy_id="p1",
                tier="silver",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                status="active",
                covered_people=["m1"],
            )
        ],
        providers=[
            Provider(
                provider_id="pr1",
                name="Al Noor Clinic",
                vat_number="300000000000003",
                city="Riyadh",
                in_network=True,
                trust_score=0.8,
            )
        ],
        histories=[
            MemberHistory(
                member_id="m1", past_claims=5, past_claims_paid=5, limits_used={"outpatient": 100}
            )
        ],
    )


def test_reference_lookups() -> None:
    ref = build_reference()
    assert ref.member("m1").display_name == "Sara"
    assert ref.policy("p1").tier == "silver"
    assert ref.provider_by_vat("300000000000003").trust_score == 0.8
    assert ref.provider_by_vat("399999999999993").provider_id == "unknown"
    assert ref.provider_by_vat(None).provider_id == "unknown"
    assert ref.history("m1").past_claims == 5
    assert ref.history("m2").past_claims == 0


def test_reference_lookup_errors_name_the_id() -> None:
    ref = build_reference()
    with pytest.raises(LookupError, match="m404"):
        ref.member("m404")
    with pytest.raises(LookupError, match="p404"):
        ref.policy("p404")


def test_money_field_value_must_be_digits() -> None:  # final review: "22.50" would pay 0 VAT
    with pytest.raises(ValidationError):
        make_field("vat_total", "22.50")
    with pytest.raises(ValidationError):
        make_field("total", "١٧٢٥٠")
    assert make_field("total", "17250").value == "17250"
