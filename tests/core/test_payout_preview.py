"""The estimate shown before submit names a used-up sub-limit in plain words."""

from reimbursement_council.core.models.reference import MemberHistory
from reimbursement_council.core.payout import calculate_payout
from reimbursement_council.core.payout_preview import estimate_lines
from tests.factories import (
    MEMBER_ID,
    make_extraction,
    make_field,
    make_item,
    make_policy,
    repo_settings,
)


def test_the_real_case_estimate_explains_the_frame_sub_limit() -> None:
    settings = repo_settings()
    history = MemberHistory(
        member_id=MEMBER_ID,
        past_claims=1,
        past_claims_paid=1,
        limits_used={"optical_frames": 60000},
    )
    reading = make_extraction(
        [make_field("vat_total", "0")],
        [make_item("OPT-FRAME", 160000), make_item("OPT-LENS", 15000)],
    )
    payout = calculate_payout(reading, make_policy(), history, settings)
    tier = settings.policy.tiers["silver"]
    english = estimate_lines(payout, tier, history, 0, settings.messages.en)
    assert english[0] == "Estimated payout: 450.00 SAR of the 1750.00 SAR you paid."
    assert english[1] == (
        "1200.00 SAR is over your eyeglass frames limit for this year "
        "(400.00 SAR of 1000.00 SAR was left)."
    )
    assert english[2] == "Your share: 100.00 SAR (20 percent, at most 100.00 SAR)."
    arabic = estimate_lines(payout, tier, history, 0, settings.messages.ar)
    assert "إطارات النظارات" in arabic[1]


def test_vat_on_the_receipt_is_named_as_not_covered() -> None:
    settings = repo_settings()
    history = MemberHistory(member_id=MEMBER_ID, past_claims=0, past_claims_paid=0, limits_used={})
    reading = make_extraction([make_field("vat_total", "2250")], [make_item("CONS-GP", 15000)])
    payout = calculate_payout(reading, make_policy(), history, settings)
    lines = estimate_lines(
        payout, settings.policy.tiers["silver"], history, 2250, settings.messages.en
    )
    assert lines[-1] == "VAT (22.50 SAR) is not covered."
