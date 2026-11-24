from collections import Counter

from reimbursement_council.synthetic.claims import DEFECTS, make_claim_set
from tests.factories import repo_settings


def test_same_seed_same_set() -> None:
    assert make_claim_set(3, 40, repo_settings()) == make_claim_set(3, 40, repo_settings())


def test_every_defect_appears_in_a_big_set() -> None:
    claim_set = make_claim_set(1, 300, repo_settings())
    seen = Counter(d for case in claim_set.cases for d in case.truth.defects)
    assert set(DEFECTS) <= set(seen) | {"clean"}
    assert sum(not case.truth.defects for case in claim_set.cases) > 100


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
    assert clean.truth.correct_payout == 15525


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
