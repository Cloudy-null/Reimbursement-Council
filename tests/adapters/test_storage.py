from pathlib import Path

from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.core.models.decision import Decision, MemberMessage
from reimbursement_council.core.rules import SeenReceipts
from tests.factories import SUBMITTED_AT


def decision(claim_id: str = "claim-a", lane: str = "auto_approve") -> Decision:
    return Decision(
        claim_id=claim_id,
        decided_at=SUBMITTED_AT,
        config_version="abc123def456",
        combined_score=0.975,
        p_good=0.975,
        disagreement=0.04,
        payout_requested=17250,
        payout_calculated=15525,
        expected_loss=388,
        reviewer_time_value=2500,
        lane=lane,  # type: ignore[arg-type]
        lane_reason="r",
        outcome="complete",
        self_fix_request=None,
        member_message=MemberMessage(en="Approved.", ar="تمت الموافقة."),
        votes=[],
        rule_results=[],
        check_results=[],
    )


def test_decision_round_trip(tmp_path: Path) -> None:
    store = ClaimStore(tmp_path / "nested" / "claims.sqlite")
    assert store.load_decision("claim-a") is None
    store.save_decision(decision())
    assert store.load_decision("claim-a") == decision()


def test_save_replaces_same_claim(tmp_path: Path) -> None:
    store = ClaimStore(tmp_path / "claims.sqlite")
    store.save_decision(decision())
    store.save_decision(decision(lane="human_review"))
    loaded = store.load_decision("claim-a")
    assert loaded is not None and loaded.lane == "human_review"


def test_seen_excludes_own_claim(tmp_path: Path) -> None:  # Review Focus 3
    store = ClaimStore(tmp_path / "claims.sqlite")
    store.record_receipt("claim-a", "hash1", "fp1", None, "auto_approve")
    assert store.seen_receipts("claim-a") == SeenReceipts(
        fingerprints=frozenset(), image_hashes=frozenset()
    )
    seen = store.seen_receipts("claim-b")
    assert "hash1" in seen.image_hashes and "fp1" in seen.fingerprints


def test_missing_parts_are_not_seen(tmp_path: Path) -> None:
    store = ClaimStore(tmp_path / "claims.sqlite")
    store.record_receipt("claim-a", None, None, None, "auto_approve")
    assert store.seen_receipts("claim-b") == SeenReceipts(
        fingerprints=frozenset(), image_hashes=frozenset()
    )


def test_store_survives_reopen(tmp_path: Path) -> None:
    ClaimStore(tmp_path / "claims.sqlite").record_receipt(
        "claim-a", "hash1", None, None, "auto_approve"
    )
    assert "hash1" in ClaimStore(tmp_path / "claims.sqlite").seen_receipts("claim-b").image_hashes


def test_rejected_claims_do_not_block_resubmission(tmp_path: Path) -> None:  # final review
    store = ClaimStore(tmp_path / "claims.sqlite")
    store.record_receipt("claim-a", "hash1", "fp1", "wk1", "auto_reject")
    assert store.seen_receipts("claim-b") == SeenReceipts(
        fingerprints=frozenset(), image_hashes=frozenset()
    )


def test_record_replaces_the_claims_old_receipt(tmp_path: Path) -> None:
    store = ClaimStore(tmp_path / "claims.sqlite")
    store.record_receipt("claim-a", "hash1", "fp1", "wk1", "auto_approve")
    store.record_receipt("claim-a", "hash1", "fp1", "wk1", "auto_reject")
    assert store.seen_receipts("claim-b").image_hashes == frozenset()


def test_weak_keys_are_seen(tmp_path: Path) -> None:
    store = ClaimStore(tmp_path / "claims.sqlite")
    store.record_receipt("claim-a", None, None, "wk1", "human_review")
    assert store.seen_receipts("claim-b").weak_keys == frozenset({"wk1"})
