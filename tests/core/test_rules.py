from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from reimbursement_council.core.models.claim import ExtractedField, ExtractionResult, LineItem
from reimbursement_council.core.models.decision import RuleResult
from reimbursement_council.core.rules import SeenReceipts, receipt_keys, run_hard_rules
from tests.factories import (
    SUBMITTED_AT,
    make_claim,
    make_extraction,
    make_field,
    make_item,
    make_policy,
    repo_settings,
)

NOTHING_SEEN = SeenReceipts(fingerprints=frozenset(), image_hashes=frozenset())
ORDER = [
    "late",
    "policy_inactive",
    "person_not_covered",
    "excluded_service",
    "duplicate",
    "multiple_patients",
]


def receipt(
    treatment_date: str = "2026-11-15",
    date_confidence: float = 0.95,
    items: list[LineItem] | None = None,
    patients: list[ExtractedField] | None = None,
    extra: list[ExtractedField] | None = None,
) -> ExtractionResult:
    fields = [
        make_field("treatment_date", treatment_date, date_confidence),
        make_field("vat_number", "300000000000003"),
        make_field("invoice_timestamp", "2026-11-15T10:30:00Z"),
        make_field("total", "17250"),
    ]
    fields += patients if patients is not None else [make_field("patient_name", "Sara Ahmed")]
    fields += extra or []
    return make_extraction(fields, items if items is not None else [make_item("CONS-GP", 15000)])


def rules(
    extraction: ExtractionResult | None = None,
    seen: SeenReceipts = NOTHING_SEEN,
    image_hash: str | None = "hash-1",
    **claim_changes: object,
) -> dict[str, RuleResult]:
    claim = make_claim(**claim_changes)  # type: ignore[arg-type]
    results = run_hard_rules(
        claim,
        make_policy(),
        receipt() if extraction is None else extraction,
        image_hash,
        seen,
        repo_settings(),
    )
    return {result.rule: result for result in results}


def outcome(extraction: ExtractionResult, rule: str, **kwargs: object) -> str:
    return rules(extraction, **kwargs)[rule].outcome  # type: ignore[arg-type]


def days_before_submission(days: int) -> str:
    return (SUBMITTED_AT.date() - timedelta(days=days)).isoformat()


def test_clean_receipt_passes_every_rule() -> None:
    results = rules()
    assert all(result.outcome == "pass" for result in results.values())
    assert all(result.reason for result in results.values())


@pytest.mark.parametrize("days, expected", [(0, "pass"), (90, "pass"), (91, "fail")])
def test_late_window(days: int, expected: str) -> None:
    assert outcome(receipt(days_before_submission(days)), "late") == expected


def test_late_not_sure_below_floor() -> None:
    assert outcome(receipt(date_confidence=0.6), "late") == "not_sure"


def test_late_not_sure_when_missing() -> None:
    extraction = make_extraction([make_field("total", "17250")])
    result = rules(extraction)["late"]
    assert result.outcome == "not_sure" and result.fields == ["treatment_date"]


def test_future_treatment_date_not_sure() -> None:
    assert outcome(receipt("2026-11-25"), "late") == "not_sure"


def test_policy_outside_dates_fails() -> None:
    old_policy = make_policy(start_date=date(2025, 1, 1), end_date=date(2025, 12, 31))
    results = run_hard_rules(
        make_claim(), old_policy, receipt(), "hash-1", NOTHING_SEEN, repo_settings()
    )
    assert results[1].rule == "policy_inactive" and results[1].outcome == "fail"


def test_policy_status_inactive_fails() -> None:
    results = run_hard_rules(
        make_claim(), make_policy(status="inactive"), receipt(), "h", NOTHING_SEEN, repo_settings()
    )
    assert results[1].outcome == "fail"


def test_policy_not_sure_with_low_confidence_date() -> None:
    assert outcome(receipt(date_confidence=0.6), "policy_inactive") == "not_sure"


def test_person_not_covered_fails() -> None:
    assert rules(patient_member_id="someone-else")["person_not_covered"].outcome == "fail"


def test_excluded_confident_fails_low_is_not_sure() -> None:
    confident = receipt(items=[make_item("DENT-WHITEN", 60000)])
    unsure = receipt(items=[make_item("DENT-WHITEN", 60000, confidence=0.5)])
    assert outcome(confident, "excluded_service") == "fail"
    assert outcome(unsure, "excluded_service") == "not_sure"


def test_duplicate_by_image_hash() -> None:
    seen = SeenReceipts(fingerprints=frozenset(), image_hashes=frozenset({"hash-1"}))
    assert rules(seen=seen)["duplicate"].outcome == "fail"


def seen_keys(fingerprint: str = "", weak_key: str = "") -> SeenReceipts:
    return SeenReceipts(
        fingerprints=frozenset({fingerprint} - {""}),
        image_hashes=frozenset(),
        weak_keys=frozenset({weak_key} - {""}),
    )


def test_receipt_keys() -> None:
    keys = receipt_keys(receipt(), 3)
    assert keys.fingerprint == "300000000000003|2026-11-15T10:30:00Z|17250"
    assert keys.weak_key == "300000000000003|2026-11-15|17250"
    empty = receipt_keys(make_extraction([]), 3)
    assert (empty.fingerprint, empty.weak_key) == (None, None)


def test_fingerprint_is_the_same_instant_in_any_zone() -> None:
    local = receipt(extra=[make_field("invoice_timestamp", "2026-11-15T13:30:00+03:00", 0.99)])
    assert receipt_keys(local, 3).fingerprint == "300000000000003|2026-11-15T10:30:00Z|17250"


def test_duplicate_by_fingerprint() -> None:
    seen = seen_keys(fingerprint="300000000000003|2026-11-15T10:30:00Z|17250")
    assert rules(seen=seen, image_hash="other-hash")["duplicate"].outcome == "fail"


def test_same_day_same_total_new_timestamp_not_duplicate() -> None:
    seen = SeenReceipts(
        fingerprints=frozenset({"300000000000003|2026-11-15T09:00:00Z|17250"}),
        image_hashes=frozenset({"other-hash"}),
    )
    assert rules(seen=seen)["duplicate"].outcome == "pass"


def test_low_confidence_fingerprint_match_is_not_sure() -> None:  # final review
    low_total = receipt(extra=[make_field("total", "17250", 0.5)])
    unclear = make_extraction(
        [f for f in low_total.fields if not (f.name == "total" and f.confidence > 0.5)]
    )
    seen = seen_keys(fingerprint="300000000000003|2026-11-15T10:30:00Z|17250")
    assert rules(unclear, seen=seen, image_hash="other")["duplicate"].outcome == "not_sure"


def test_same_provider_date_and_total_is_not_sure() -> None:  # final review: new photo, no QR
    no_timestamp = make_extraction([f for f in receipt().fields if f.name != "invoice_timestamp"])
    seen = seen_keys(weak_key="300000000000003|2026-11-15|17250")
    assert rules(no_timestamp, seen=seen, image_hash="other")["duplicate"].outcome == "not_sure"


def test_claimant_must_be_on_the_policy() -> None:  # final review
    stranger = make_claim().model_copy(update={"member_id": "someone-else"})
    results = run_hard_rules(stranger, make_policy(), receipt(), "h", NOTHING_SEEN, repo_settings())
    assert results[2].rule == "person_not_covered" and results[2].outcome == "fail"


def test_two_patients_fail_same_name_spacing_passes() -> None:
    two = [make_field("patient_name", "Sara Ahmed"), make_field("patient_name", "Omar Ahmed")]
    same = [make_field("patient_name", "Sara  Ahmed"), make_field("patient_name", "sara ahmed")]
    unsure = [make_field("patient_name", "Sara Ahmed"), make_field("patient_name", "Omar", 0.5)]
    assert outcome(receipt(patients=two), "multiple_patients") == "fail"
    assert outcome(receipt(patients=same), "multiple_patients") == "pass"
    assert outcome(receipt(patients=unsure), "multiple_patients") == "not_sure"


def test_no_extraction() -> None:
    results = {
        result.rule: result
        for result in run_hard_rules(
            make_claim(), make_policy(), None, None, NOTHING_SEEN, repo_settings()
        )
    }
    assert results["late"].outcome == "not_sure" and results["late"].fields == ["receipt"]
    assert results["policy_inactive"].outcome == "not_sure"
    assert results["policy_inactive"].fields == ["receipt"]
    for rule in ("person_not_covered", "excluded_service", "duplicate", "multiple_patients"):
        assert results[rule].outcome == "pass"


def test_result_order() -> None:
    results = run_hard_rules(
        make_claim(), make_policy(), receipt(), "hash-1", NOTHING_SEEN, repo_settings()
    )
    assert [result.rule for result in results] == ORDER


def test_late_uses_local_date_of_submission() -> None:  # final review: timezone
    # 22:00 UTC on 2026-11-20 is 01:00 on 2026-11-21 in Riyadh: 91 days after 2026-08-22
    late_evening = datetime(2026, 11, 20, 22, 0, tzinfo=UTC)
    same_instant = datetime(2026, 11, 21, 1, 0, tzinfo=timezone(timedelta(hours=3)))
    for submitted in (late_evening, same_instant):
        assert rules(receipt("2026-08-22"), submitted_at=submitted)["late"].outcome == "fail"
        assert rules(receipt("2026-08-23"), submitted_at=submitted)["late"].outcome == "pass"


def test_same_day_after_midnight_local_is_not_future() -> None:
    submitted = datetime(2026, 11, 19, 23, 0, tzinfo=UTC)  # 02:00 on 2026-11-20 in Riyadh
    assert rules(receipt("2026-11-20"), submitted_at=submitted)["late"].outcome == "pass"
