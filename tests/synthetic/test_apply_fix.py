"""run-set --simulate-fix: the member sends the fixed file and the claim is tried again."""

from datetime import UTC, datetime
from pathlib import Path

from reimbursement_council.core.models.decision import SelfFixRequest
from reimbursement_council.synthetic.apply_fix import claim_after_fix
from reimbursement_council.synthetic.claims import make_claim_set
from tests.factories import repo_settings

NOW = datetime(2026, 11, 25, tzinfo=UTC)


def a_claim():  # type: ignore[no-untyped-def]
    case = next(c for c in make_claim_set(2, 60, repo_settings()).cases if c.extra_documents)
    return case.claim


def test_a_replacing_fix_swaps_the_document_and_counts_a_retry() -> None:
    claim = a_claim()
    wrong = claim.documents[1].document_id
    fix = {"file": "x-fix.png", "kind": "medical_report", "replace": wrong}
    request = SelfFixRequest(kind="fix_mismatch", field="patient_name", text="t")
    fixed = claim_after_fix(claim, fix, Path("set"), request, NOW)
    ids = [d.document_id for d in fixed.documents]
    assert wrong not in ids and ids[-1] == f"{claim.claim_id}-fix"
    assert fixed.documents[-1].file_path == str(Path("set") / "x-fix.png")
    assert fixed.retries_used == claim.retries_used + 1 and fixed.retake_fields == ["patient_name"]


def test_an_adding_fix_keeps_every_document_and_does_not_mark_add_document_as_asked() -> None:
    claim = a_claim()
    fix = {"file": "x-fix.png", "kind": "prescription", "replace": None}
    request = SelfFixRequest(kind="add_document", field="prescription", text="t")
    fixed = claim_after_fix(claim, fix, Path("set"), request, NOW)
    assert len(fixed.documents) == len(claim.documents) + 1 and fixed.retake_fields == []
