"""End to end data test: every fixture claim goes through the whole pipeline."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from reimbursement_council.adapters.files import load_claim_file, load_reference_file
from reimbursement_council.adapters.readers import FixtureReader
from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.core.models.claim import Claim, FieldEdit
from reimbursement_council.core.models.decision import Decision
from reimbursement_council.pipeline.process_claim import process_claim
from tests.factories import repo_settings

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
CLAIMS = FIXTURES / "claims"
NOW = datetime(2026, 11, 20, 9, 5, tzinfo=UTC)
NEW_ID = "00000000-0000-4000-8000-0000000000f1"


def load(name: str) -> Claim:
    return load_claim_file(CLAIMS / f"{name}.claim.json")


def run(claim: Claim, store: ClaimStore) -> Decision:
    reference = load_reference_file(FIXTURES / "reference.json")
    return process_claim(claim, reference, repo_settings(), store, NOW)


@pytest.mark.parametrize(
    "name, lane",
    [
        ("clean", "auto_approve"),
        ("late", "auto_reject"),
        ("blurry_date", "self_fix"),
        ("blurry_date_no_retries", "human_review"),
        ("overpriced", "human_review"),
        ("unlisted_service", "human_review"),
        ("prescription_only", "self_fix"),
    ],
)
def test_fixture_lanes(name: str, lane: str, tmp_path: Path) -> None:
    decision = run(load(name), ClaimStore(tmp_path / "claims.sqlite"))
    assert decision.lane == lane, decision.lane_reason
    assert decision.member_message.en and decision.member_message.ar


def test_clean_details(tmp_path: Path) -> None:
    decision = run(load("clean"), ClaimStore(tmp_path / "claims.sqlite"))
    assert (decision.outcome, decision.payout_calculated, decision.payout_requested) == (
        "complete",
        15525,
        17250,
    )
    assert decision.expected_loss is not None and decision.expected_loss < 2500
    assert decision.member_message.en == "Your claim is approved. We will send you 155.25 SAR."


def test_late_details(tmp_path: Path) -> None:
    decision = run(load("late"), ClaimStore(tmp_path / "claims.sqlite"))
    late = next(r for r in decision.rule_results if r.rule == "late")
    assert late.outcome == "fail"


def test_blurry_date_asks_to_confirm(tmp_path: Path) -> None:
    decision = run(load("blurry_date"), ClaimStore(tmp_path / "claims.sqlite"))
    request = decision.self_fix_request
    assert request is not None
    assert (request.kind, request.field) == ("confirm_field", "treatment_date")


def test_overpriced_is_capped(tmp_path: Path) -> None:
    decision = run(load("overpriced"), ClaimStore(tmp_path / "claims.sqlite"))
    assert (decision.payout_calculated, decision.payout_requested) == (15525, 46000)
    assert "disagreement" in decision.lane_reason


def test_unlisted_service_names_the_item(tmp_path: Path) -> None:  # Review Focus 4
    decision = run(load("unlisted_service"), ClaimStore(tmp_path / "claims.sqlite"))
    assert "Physio session" in decision.lane_reason


def test_prescription_only_asks_for_receipt(tmp_path: Path) -> None:
    decision = run(load("prescription_only"), ClaimStore(tmp_path / "claims.sqlite"))
    request = decision.self_fix_request
    assert request is not None and (request.kind, request.field) == ("add_document", "receipt")
    assert decision.payout_calculated is None and decision.expected_loss is None


def test_decision_is_stored(tmp_path: Path) -> None:
    store = ClaimStore(tmp_path / "claims.sqlite")
    decision = run(load("clean"), store)
    assert store.load_decision(decision.claim_id) == decision


def test_same_receipt_new_claim_is_duplicate(tmp_path: Path) -> None:  # Review Focus 3
    store = ClaimStore(tmp_path / "claims.sqlite")
    clean = load("clean")
    assert run(clean, store).lane == "auto_approve"
    second = run(clean.model_copy(update={"claim_id": NEW_ID}), store)
    assert second.lane == "auto_reject"
    assert any(r.rule == "duplicate" and r.outcome == "fail" for r in second.rule_results)


def test_resubmitting_same_claim_is_not_duplicate(tmp_path: Path) -> None:  # Review Focus 3
    store = ClaimStore(tmp_path / "claims.sqlite")
    run(load("clean"), store)
    assert run(load("clean"), store).lane == "auto_approve"


FIXTURE_ORDER = [
    ("clean", "auto_approve"),
    ("late", "auto_reject"),
    ("blurry_date", "self_fix"),
    ("blurry_date_no_retries", "human_review"),
    ("overpriced", "human_review"),
    ("unlisted_service", "human_review"),
    ("prescription_only", "self_fix"),
]


def test_all_fixtures_in_one_store(tmp_path: Path) -> None:  # final review: shared database
    store = ClaimStore(tmp_path / "claims.sqlite")
    assert [(name, run(load(name), store).lane) for name, _ in FIXTURE_ORDER] == FIXTURE_ORDER


def test_rejected_then_resent_correctly_is_not_duplicate(tmp_path: Path) -> None:  # final review
    store = ClaimStore(tmp_path / "claims.sqlite")
    clean = load("clean")
    wrong_patient = clean.model_copy(update={"patient_member_id": "not-on-policy"})
    assert run(wrong_patient, store).lane == "auto_reject"
    assert run(clean.model_copy(update={"claim_id": NEW_ID}), store).lane == "auto_approve"


def claim_with_reading(tmp_path: Path, claim_id: str, reading: dict, extra: str = "") -> Claim:
    folder = tmp_path / claim_id
    folder.mkdir()
    (folder / "r.reading.json").write_text(json.dumps(reading) + extra, encoding="utf-8")
    report = (CLAIMS / "report_clean.reading.json").read_text(encoding="utf-8")
    (folder / "report_clean.reading.json").write_text(report, encoding="utf-8")
    claim = json.loads((CLAIMS / "clean.claim.json").read_text(encoding="utf-8"))
    claim["claim_id"] = claim_id
    claim["documents"][0]["file_path"] = "r.reading.json"
    (folder / "c.claim.json").write_text(json.dumps(claim), encoding="utf-8")
    return load_claim_file(folder / "c.claim.json")


def test_new_photo_of_receipt_without_qr_goes_to_human(tmp_path: Path) -> None:  # final review
    reading = json.loads((CLAIMS / "clean.reading.json").read_text(encoding="utf-8"))
    reading["qr_payloads"] = []
    store = ClaimStore(tmp_path / "claims.sqlite")
    first = run(claim_with_reading(tmp_path, "claim-first", reading), store)
    second = run(claim_with_reading(tmp_path, "claim-second", reading, extra="\n"), store)
    assert first.lane == "auto_approve"
    assert second.lane == "human_review" and "duplicate" in second.lane_reason


def test_real_self_fix_resubmission_is_decided(tmp_path: Path) -> None:  # Review Focus 3
    store = ClaimStore(tmp_path / "claims.sqlite")
    assert run(load("blurry_date"), store).lane == "self_fix"
    reading = json.loads((CLAIMS / "blurry_date.reading.json").read_text(encoding="utf-8"))
    for field in reading["fields"]:
        if field["name"] == "treatment_date":
            field["confidence"] = 0.99  # the member confirmed the date
    fixed = claim_with_reading(tmp_path, "resend", reading)
    resent = fixed.model_copy(update={"claim_id": load("blurry_date").claim_id, "retries_used": 1})
    decision = run(resent, store)
    assert decision.lane == "auto_approve"
    assert not any(r.rule == "duplicate" and r.outcome != "pass" for r in decision.rule_results)


def test_overpriced_and_unlisted_payout_details(tmp_path: Path) -> None:
    store = ClaimStore(tmp_path / "claims.sqlite")
    unlisted = run(load("unlisted_service"), store)
    assert (unlisted.payout_requested, unlisted.payout_calculated) == (23000, 0)


def test_clean_claim_has_its_medical_report() -> None:
    kinds = sorted(d.kind for d in load("clean").documents)
    assert kinds == ["medical_report", "receipt"]


def test_outpatient_claim_without_its_report_is_not_auto_approved(tmp_path: Path) -> None:
    clean = load("clean")
    receipt_only = clean.model_copy(
        update={"documents": [d for d in clean.documents if d.kind == "receipt"]}
    )
    decision = run(receipt_only, ClaimStore(tmp_path / "db.sqlite"))
    assert decision.lane != "auto_approve"
    assert "medical_report" in decision.lane_reason or decision.self_fix_request is not None


def test_judged_edits_are_kept_on_the_decision(tmp_path: Path) -> None:
    clean = load("clean")
    receipt_id = next(d.document_id for d in clean.documents if d.kind == "receipt")
    edit = FieldEdit(document_id=receipt_id, field="total", read_value="17250", typed_value="27250")
    decision = run(clean.model_copy(update={"edits": [edit]}), ClaimStore(tmp_path / "db.sqlite"))
    assert [e.evidence for e in decision.edits] == ["contradicts"]
    assert any(r.rule == "member_edit" for r in decision.rule_results)


def test_stored_readings_are_used(tmp_path: Path) -> None:
    clean = load("clean")
    readings = {d.document_id: FixtureReader().read(d) for d in clean.documents}
    moved = clean.model_copy(
        update={
            "documents": [
                d.model_copy(update={"file_path": "gone.reading.json"}) for d in clean.documents
            ]
        }
    )
    reference = load_reference_file(FIXTURES / "reference.json")
    decision = process_claim(
        moved,
        reference,
        repo_settings(),
        ClaimStore(tmp_path / "db.sqlite"),
        NOW,
        readings=readings,
    )
    assert decision.lane == "auto_approve"
