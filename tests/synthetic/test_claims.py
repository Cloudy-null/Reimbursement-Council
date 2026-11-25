from collections import Counter

from reimbursement_council.synthetic.claims import DEFECTS, make_claim_set
from tests.factories import repo_settings


def test_same_seed_same_set() -> None:
    assert make_claim_set(3, 40, repo_settings()) == make_claim_set(3, 40, repo_settings())


def test_every_defect_appears_in_a_big_set() -> None:
    claim_set = make_claim_set(1, 300, repo_settings())
    seen = Counter(d for case in claim_set.cases for d in case.truth.defects)
    assert set(DEFECTS) <= set(seen) | {"clean"}
    # clean is 45 of 124 weight since the document defects (Task 10), about 109 of 300
    assert sum(not case.truth.defects for case in claim_set.cases) > 80


def test_hard_rule_defects_should_not_be_paid() -> None:
    claim_set = make_claim_set(1, 300, repo_settings())
    for case in claim_set.cases:
        hard = {"late", "inactive", "not_covered", "excluded", "duplicate"} & set(
            case.truth.defects
        )
        assert case.truth.should_pay is not bool(hard)
        if hard:
            assert case.truth.correct_payout == 0


def test_clean_case_payout_follows_policy() -> None:
    claim_set = make_claim_set(1, 300, repo_settings())
    clean = next(
        c
        for c in claim_set.cases
        if not c.truth.defects
        and c.receipt.items[0].service_code == "CONS-GP"
        and len(c.receipt.items) == 1
    )
    # 150.00 consultation: 10 percent co-pay, VAT on the paid part
    assert clean.truth.correct_payout == 13500


def test_duplicate_reuses_an_earlier_receipt() -> None:
    claim_set = make_claim_set(1, 300, repo_settings())
    names = [case.name for case in claim_set.cases]
    for index, case in enumerate(claim_set.cases):
        if "duplicate" in case.truth.defects:
            assert case.duplicate_of in names[:index]
            original = claim_set.cases[names.index(case.duplicate_of)]
            assert original.receipt == case.receipt


def test_claims_point_at_their_receipt_and_known_people() -> None:
    claim_set = make_claim_set(2, 60, repo_settings())
    members = {m.member_id for m in claim_set.reference.members}
    for case in claim_set.cases:
        assert case.claim.documents[0].file_path == f"{case.name}.png"
        assert case.claim.member_id in members and case.claim.patient_member_id in members
        assert case.claim.submitted_at.tzinfo is not None


def test_duplicates_can_be_caught_and_keep_the_original_defects() -> None:
    # A duplicate must be sent after its original, copy a receipt that can be read (an
    # unreadable original leaves nothing to match, so the copy is really an honest retake),
    # and keep the original's defects.
    for seed in (11, 12):
        cases = make_claim_set(seed, 120, repo_settings()).cases
        by_name = {c.name: c for c in cases}
        duplicates = [c for c in cases if c.duplicate_of]
        assert duplicates
        for case in duplicates:
            original = by_name[case.duplicate_of or ""]
            assert case.claim.submitted_at > original.claim.submitted_at, case.name
            assert original.damage != "unreadable", case.name
            assert set(original.truth.defects) | {"duplicate"} == set(case.truth.defects)


def test_defect_weights_come_from_config() -> None:
    from reimbursement_council.config.models import SyntheticConfig

    settings = repo_settings()
    only_late = SyntheticConfig(qr_share=0.0, defect_weights={"late": 1})
    claim_set = make_claim_set(3, 20, settings.model_copy(update={"synthetic": only_late}))
    assert all(case.truth.defects == ["late"] for case in claim_set.cases)
    assert all(case.receipt.qr_payload is None for case in claim_set.cases)


def test_a_defect_the_generator_cannot_make_is_refused() -> None:
    import pytest

    from reimbursement_council.config.models import SyntheticConfig

    settings = repo_settings().model_copy(
        update={"synthetic": SyntheticConfig(qr_share=0.5, defect_weights={"made_up": 1})}
    )
    with pytest.raises(ValueError, match="made_up"):
        make_claim_set(3, 5, settings)


def test_the_repo_config_weights_name_every_known_defect() -> None:
    from reimbursement_council.synthetic.claims import KNOWN_DEFECTS

    assert set(repo_settings().synthetic.defect_weights) == set(KNOWN_DEFECTS)


# sha256 of make_claim_set(seed, count).model_dump_json(), taken before the optical, dental,
# damage and language generators were added (core day 4b gen). Same seed, same claims.
SNAPSHOTS = {
    (1, 200): "b5b7441a5dd9c84f73eaa5fd9387b60a74312efd6eb75eee17c7df618eb86b28",
    (7, 60): "480a321f79215a81fab33f72469a6c17ab0dc5e2c4cdcf901899c4d2e1c52b51",
}


def test_make_claims_is_unchanged_for_the_same_seed() -> None:
    import hashlib

    for (seed, count), expected in SNAPSHOTS.items():
        dump = make_claim_set(seed, count, repo_settings()).model_dump_json()
        assert hashlib.sha256(dump.encode()).hexdigest() == expected, (seed, count)


def test_set_only_defects_are_known_with_weight_zero() -> None:
    from reimbursement_council.synthetic.claims import KNOWN_DEFECTS, SET_ONLY_DEFECTS

    weights = repo_settings().synthetic.defect_weights
    assert set(SET_ONLY_DEFECTS) == {
        "missing_eye_test",
        "missing_payment_proof",
        "invalid_invoice",
        "missing_tooth_number",
    }
    assert set(SET_ONLY_DEFECTS) <= set(KNOWN_DEFECTS)
    assert not set(SET_ONLY_DEFECTS) & set(DEFECTS)
    assert all(weights[name] == 0 for name in SET_ONLY_DEFECTS)


def test_make_claims_refuses_a_weight_on_a_set_only_defect() -> None:
    import pytest

    from reimbursement_council.config.models import SyntheticConfig

    settings = repo_settings().model_copy(
        update={
            "synthetic": SyntheticConfig(
                qr_share=0.5, defect_weights={"clean": 1, "missing_eye_test": 1}
            )
        }
    )
    with pytest.raises(ValueError, match="missing_eye_test"):
        make_claim_set(3, 5, settings)
