from reimbursement_council.core.decision.document_requests import (
    DUPLICATE_REASON,
    human_reasons,
    member_requests,
)
from reimbursement_council.core.models.claim import FieldEdit
from reimbursement_council.core.models.decision import (
    CrossCheckResult,
    DocumentNeed,
    MemberMessage,
    RuleResult,
)
from tests.factories import repo_settings


def need(*group: str, satisfied: bool = False) -> DocumentNeed:
    return DocumentNeed(
        group=list(group),  # type: ignore[arg-type]
        satisfied=satisfied,
        request=MemberMessage(en=f"Please add {group[0]}.", ar="أضف"),
    )


def mismatch(field: str = "patient_name") -> CrossCheckResult:
    return CrossCheckResult(
        name="patient_matches_account",
        passed=False,
        field=field,  # type: ignore[arg-type]
        document_ids=["d1", "d2"],
        details="names differ",
    )


def edit(field: str, evidence: str, typed: str = "17250") -> FieldEdit:
    return FieldEdit(
        document_id="d1",
        field=field,
        read_value=None,
        typed_value=typed,  # type: ignore[arg-type]
        evidence=evidence,  # type: ignore[arg-type]
    )


def test_order_is_missing_then_mismatch_then_retake() -> None:
    requests = member_requests(
        [need("prescription"), need("invoice", "receipt", satisfied=True)],
        [mismatch()],
        [edit("total", "none")],
        [],
        repo_settings(),
    )
    assert [(r.kind, r.field) for r in requests] == [
        ("add_document", "prescription"),
        ("confirm_field", "patient_name"),
        ("retake_photo", "total"),
    ]
    assert requests[0].text == "Please add prescription."


def test_unknown_cross_check_and_supported_edits_ask_nothing() -> None:
    unknown = mismatch().model_copy(update={"passed": None})
    requests = member_requests(
        [],
        [unknown],
        [edit("total", "supports"), edit("provider_name", "none", "X")],
        [],
        repo_settings(),
    )
    assert requests == []


def test_retake_is_asked_only_once() -> None:
    assert member_requests([], [], [edit("total", "none")], ["total"], repo_settings()) == []


def test_human_reasons() -> None:
    contradicting = RuleResult(
        rule="member_edit", outcome="not_sure", reason="typed 200, shows 172", fields=["total"]
    )
    duplicate = RuleResult(rule="duplicate", outcome="not_sure", reason="same", fields=[])
    passed = RuleResult(rule="late", outcome="pass", reason="ok", fields=[])
    reasons = human_reasons(
        [contradicting, duplicate, passed],
        [edit("total", "none"), edit("vat_total", "none")],
        ["total"],
    )
    assert reasons[0] == "typed 200, shows 172"
    assert reasons[1] == DUPLICATE_REASON
    assert len(reasons) == 3 and "total" in reasons[2] and "vat_total" not in reasons[2]
