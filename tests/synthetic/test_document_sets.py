"""Task 10: synthetic claims carry document sets with known truth (spec 6.6)."""

from functools import cache

from reimbursement_council.synthetic.claims import PEOPLE, SyntheticSet, make_claim_set, member_id
from reimbursement_council.synthetic.document_sets import DOCUMENT_DEFECTS, add_documents
from tests.factories import repo_settings


@cache
def big_set() -> SyntheticSet:
    return make_claim_set(1, 400, repo_settings())


def categories(case) -> set[str]:  # type: ignore[no-untyped-def]
    prices = repo_settings().prices
    return {prices[i.service_code].category for i in case.receipt.items if i.service_code in prices}


def test_every_document_defect_appears() -> None:
    seen = {d for case in big_set().cases for d in case.truth.defects}
    assert set(DOCUMENT_DEFECTS) <= seen


def test_pharmacy_case_gets_a_prescription_unless_missing() -> None:
    pharmacy = [c for c in big_set().cases if "pharmacy" in categories(c)]
    assert pharmacy
    for case in pharmacy:
        kinds = set(case.truth.document_kinds.values())
        if "missing_prescription" in case.truth.defects:
            assert "prescription" not in kinds and ["prescription"] in case.truth.needs_missing
        else:
            assert "prescription" in kinds


def test_receipt_is_the_same_when_only_documents_change() -> None:
    case = next(c for c in big_set().cases if not c.truth.defects)
    plain = case.model_copy(
        update={
            "extra_documents": [],
            "truth": case.truth.model_copy(update={"document_kinds": {}}),
        }
    )
    again = add_documents(plain, "date_mismatch", 1, 7, repo_settings())
    assert again.receipt == case.receipt
    assert add_documents(plain, "date_mismatch", 1, 7, repo_settings()) == again


def test_name_mismatch_puts_another_known_person_on_the_second_document() -> None:
    case = next(c for c in big_set().cases if "patient_name_mismatch" in c.truth.defects)
    patient = case.receipt.patient
    others = [d.content.patient for d in case.extra_documents]
    assert others and all(p in PEOPLE for p in others) and patient not in others
    assert case.claim.patient_member_id == member_id(PEOPLE.index(patient))


def test_date_mismatch_moves_the_second_document_date() -> None:
    case = next(c for c in big_set().cases if "date_mismatch" in c.truth.defects)
    assert all(
        d.content.issued_at.date() != case.receipt.issued_at.date() for d in case.extra_documents
    )
    assert case.truth.expected_lane == "self_fix"


def test_contradicting_edit_types_a_total_the_qr_disagrees_with() -> None:
    case = next(c for c in big_set().cases if "member_edit_contradicts" in c.truth.defects)
    assert case.receipt.qr_payload is not None
    (edit,) = case.claim.edits
    assert edit.field == "total" and edit.typed_value != str(case.receipt.total)
    assert case.truth.expected_lane == "human_review"


def test_supported_edit_types_the_true_total() -> None:
    case = next(c for c in big_set().cases if "member_edit_supported" in c.truth.defects)
    (edit,) = case.claim.edits
    assert edit.typed_value == str(case.receipt.total) and case.truth.expected_lane is None


def test_truth_lists_kinds_missing_needs_and_expected_lane() -> None:
    cases = big_set().cases
    clean = next(c for c in cases if not c.truth.defects and categories(c) == {"outpatient"})
    assert sorted(clean.truth.document_kinds.values()) == ["invoice", "medical_report"]
    assert clean.truth.needs_missing == [] and clean.truth.expected_lane is None
    missing = next(c for c in cases if "missing_medical_report" in c.truth.defects)
    assert missing.truth.needs_missing == [["medical_report"]]
    assert missing.truth.expected_lane == "self_fix"
    assert set(missing.truth.document_kinds) == {d.document_id for d in missing.claim.documents}


def test_members_have_arabic_names() -> None:
    reference = big_set().reference
    assert all(m.name_ar for m in reference.members)


def test_a_duplicate_never_carries_an_edit_label_without_the_edit() -> None:
    for case in big_set().cases:
        if case.duplicate_of and set(case.truth.defects) & {
            "member_edit_supported",
            "member_edit_contradicts",
        }:
            assert case.claim.edits
