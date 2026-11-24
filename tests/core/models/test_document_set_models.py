from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from reimbursement_council.adapters.files import load_claim_file
from reimbursement_council.core.models.case import ClaimCase
from reimbursement_council.core.models.claim import FieldEdit, ReaderOutput
from reimbursement_council.core.models.common import RULE_FIELDS
from reimbursement_council.core.models.decision import CrossCheckResult, DocumentNeed, MemberMessage
from reimbursement_council.core.models.reference import Member

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "claims"


def test_old_claim_json_still_loads() -> None:
    old = load_claim_file(FIXTURES / "clean.claim.json")
    assert old.edits == [] and old.claim_categories == [] and old.retake_fields == []
    assert old.detected_categories == []
    assert all(d.kind_source == "detected" and d.detected_kind is None for d in old.documents)


def test_field_edit_needs_known_evidence() -> None:
    with pytest.raises(ValidationError):
        FieldEdit(
            document_id="d", field="total", read_value="100", typed_value="1", evidence="maybe"
        )


def test_field_edit_starts_with_no_evidence() -> None:
    edit = FieldEdit(document_id="d", field="total", read_value=None, typed_value="17250")
    assert edit.evidence == "none" and edit.evidence_note == ""


def test_member_name_ar_is_optional() -> None:
    member = Member(member_id="m", display_name="Sara", date_joined=date(2023, 1, 1), policy_id="p")
    assert member.name_ar is None


def test_cross_check_passed_can_be_unknown() -> None:
    result = CrossCheckResult(
        name="dates_agree", passed=None, field="treatment_date", document_ids=[], details="no dates"
    )
    assert result.passed is None


def test_document_need_carries_a_request_in_both_languages() -> None:
    need = DocumentNeed(
        group=["prescription"], satisfied=False, request=MemberMessage(en="Add it", ar="أضفها")
    )
    assert need.request.ar == "أضفها"


def test_reader_output_text_lines_default_empty() -> None:
    assert ReaderOutput(fields=[], line_items=[], qr_payloads=[]).text_lines == []


def test_rule_fields_cover_money_and_hard_rule_inputs() -> None:
    assert {"total", "treatment_date", "patient_name", "vat_number"} <= RULE_FIELDS
    assert "provider_name" not in RULE_FIELDS


def test_claim_case_document_fields_default_empty() -> None:
    fields = ClaimCase.model_fields
    assert fields["documents_read"].default_factory is not None
    assert fields["needs"].default_factory is not None
    assert fields["cross_checks"].default_factory is not None
