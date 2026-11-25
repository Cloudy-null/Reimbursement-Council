"""Fixed versions of fixable defects, so self-fix can be measured (spec 7)."""

from functools import cache

from reimbursement_council.synthetic.cases import SyntheticCase
from reimbursement_council.synthetic.claims import SyntheticSet, make_claim_set
from reimbursement_council.synthetic.fixes import FIXABLE_DEFECTS, MISMATCH_DEFECTS
from tests.factories import repo_settings


@cache
def big_set() -> SyntheticSet:
    return make_claim_set(2, 300, repo_settings())


def own_defect(case: SyntheticCase) -> str | None:
    return None if case.duplicate_of or not case.truth.defects else case.truth.defects[-1]


def test_every_fixable_case_has_a_fix_and_no_other_case_does() -> None:
    for case in big_set().cases:
        fixable = own_defect(case) in FIXABLE_DEFECTS
        if own_defect(case) in MISMATCH_DEFECTS and not case.extra_documents:
            fixable = False
        assert (case.fix is not None) == fixable, (case.name, case.truth.defects)


def test_an_unreadable_receipt_is_replaced_by_a_clear_photo() -> None:
    case = next(c for c in big_set().cases if own_defect(c) == "unreadable")
    assert case.fix is not None and case.fix.clinical is None
    assert case.fix.replace_document_id == case.claim.documents[0].document_id


def test_a_missing_document_is_added_for_the_right_patient() -> None:
    case = next(c for c in big_set().cases if own_defect(c) == "missing_prescription")
    assert case.fix is not None and case.fix.replace_document_id is None
    assert case.fix.clinical is not None and case.fix.clinical.kind == "prescription"
    assert case.fix.clinical.patient == case.receipt.patient


def test_a_mismatch_fix_puts_the_right_patient_and_day_on_the_same_document() -> None:
    for defect in MISMATCH_DEFECTS:
        case = next(c for c in big_set().cases if own_defect(c) == defect)
        assert case.fix is not None and case.fix.clinical is not None
        assert case.fix.replace_document_id == case.extra_documents[0].document_id
        assert case.fix.clinical.patient == case.receipt.patient
        assert case.fix.clinical.issued_at.date() == case.receipt.issued_at.date()


def test_fix_plans_do_not_change_the_claims() -> None:
    small = make_claim_set(2, 40, repo_settings()).cases
    assert [c.model_copy(update={"fix": None}) for c in small] == [
        c.model_copy(update={"fix": None}) for c in big_set().cases[:40]
    ]
