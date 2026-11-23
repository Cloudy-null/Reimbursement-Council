"""End to end data test: every fixture claim goes through the whole pipeline."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from reimbursement_council.adapters.files import load_claim_file, load_reference_file
from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.core.models.claim import Claim
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
