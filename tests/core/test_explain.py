from reimbursement_council.core.decision.lanes import LaneChoice
from reimbursement_council.core.explain import build_member_message
from reimbursement_council.core.models.decision import PayoutResult, RuleResult, SelfFixRequest
from tests.factories import repo_settings

PAYOUT = PayoutResult(
    requested=17250,
    network_cap_cut=0,
    copay=1500,
    limit_cut=0,
    vat_paid=2025,
    calculated=15525,
    unmatched_items=[],
    is_partial=False,
)
PARTIAL = PAYOUT.model_copy(
    update={"requested": 46000, "network_cap_cut": 25000, "is_partial": True}
)
LATE = [
    RuleResult(rule="late", outcome="fail", reason="r", fields=["treatment_date"]),
    RuleResult(rule="duplicate", outcome="pass", reason="r", fields=[]),
]


def choice(lane: str, request: SelfFixRequest | None = None, outcome: str = "queued") -> LaneChoice:
    return LaneChoice(lane=lane, outcome=outcome, reason="r", request=request)  # type: ignore[arg-type]


def test_approved() -> None:
    m = build_member_message(
        choice("auto_approve", outcome="complete"), [], PAYOUT, repo_settings()
    )
    assert m.en == "Your claim is approved. We will send you 155.25 SAR."
    assert m.ar == "تمت الموافقة على مطالبتك. سنحول لك 155.25 ريال."


def test_partial() -> None:
    m = build_member_message(
        choice("auto_approve", outcome="partial"), [], PARTIAL, repo_settings()
    )
    assert "155.25" in m.en and "460.00" in m.en and "in part" in m.en
    assert "155.25" in m.ar and "460.00" in m.ar


def test_rejected_late() -> None:
    m = build_member_message(
        choice("auto_reject", outcome="complete"), LATE, PAYOUT, repo_settings()
    )
    assert m.en == (
        "Your claim was not approved. Reason: "
        "The treatment date is more than 90 days before you sent the claim."
    )
    assert "90" in m.ar


def test_self_fix_confirm_date() -> None:
    request = SelfFixRequest(kind="confirm_field", field="treatment_date", text="t")
    m = build_member_message(choice("self_fix", request), [], None, repo_settings())
    assert m.en == (
        "We need one thing from you to finish your claim. "
        "Please check the treatment date we read and fix it if needed."
    )
    assert "تاريخ العلاج" in m.ar


def test_self_fix_add_receipt() -> None:
    request = SelfFixRequest(kind="add_document", field="receipt", text="t")
    m = build_member_message(choice("self_fix", request), [], None, repo_settings())
    assert m.en.endswith("Please add a receipt.")
    assert m.ar.endswith("أضف إيصال من فضلك.")


def test_human_review() -> None:
    m = build_member_message(choice("human_review"), [], None, repo_settings())
    assert m.en == (
        "A reviewer from our team will look at your claim. "
        "We will tell you the result when it is done."
    )
    assert m.ar.startswith("سيراجع")


def test_unknown_field_label_falls_back_to_name() -> None:
    request = SelfFixRequest(kind="confirm_field", field="subtotal", text="t")
    m = build_member_message(choice("self_fix", request), [], None, repo_settings())
    assert "subtotal" in m.en and "subtotal" in m.ar


def test_approved_without_payout_is_an_error() -> None:
    try:
        build_member_message(choice("auto_approve", outcome="complete"), [], None, repo_settings())
    except ValueError as error:
        assert "payout" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_missing_document_is_named_in_both_languages() -> None:
    request = SelfFixRequest(kind="add_document", field="prescription", text="t")
    m = build_member_message(choice("self_fix", request), [], None, repo_settings())
    assert "prescription" in m.en and "وصفة طبية" in m.ar
