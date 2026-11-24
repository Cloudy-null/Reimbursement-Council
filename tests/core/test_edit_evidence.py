from reimbursement_council.core.edit_evidence import apply_edits, judge_edit
from reimbursement_council.core.models.claim import (
    ExtractedField,
    ExtractionResult,
    FieldEdit,
    ReaderOutput,
)
from reimbursement_council.core.models.common import FieldName, FieldSource
from tests.factories import repo_settings


def field(
    document_id: str, name: FieldName, value: str, source: FieldSource = "ocr"
) -> ExtractedField:
    return ExtractedField(
        document_id=document_id,
        name=name,
        value=value,
        original_text=value,
        source=source,
        confidence=0.95,
    )


def reading(document_id: str, *fields: ExtractedField) -> ExtractionResult:
    return ExtractionResult(document_id=document_id, fields=list(fields), line_items=[], checks=[])


def edit(name: FieldName, typed: str, read: str | None = None, document_id: str = "r") -> FieldEdit:
    return FieldEdit(document_id=document_id, field=name, read_value=read, typed_value=typed)


def test_total_edit_matching_the_qr_supports() -> None:
    own = reading("r", field("r", "total", "71250"), field("r", "total", "17250", "qr"))
    judged = judge_edit(edit("total", "17250", "71250"), own, [], repo_settings())
    assert judged.evidence == "supports" and "QR" in judged.evidence_note


def test_total_edit_against_the_qr_contradicts_and_names_the_qr() -> None:
    own = reading("r", field("r", "total", "17250"), field("r", "total", "17250", "qr"))
    judged = judge_edit(edit("total", "71250", "17250"), own, [], repo_settings())
    assert judged.evidence == "contradicts" and "QR" in judged.evidence_note


def test_date_edit_matching_the_prescription_supports() -> None:
    own = reading("r", field("r", "treatment_date", "2026-11-02"))
    other = reading("p", field("p", "treatment_date", "2026-11-20"))
    judged = judge_edit(
        edit("treatment_date", "2026-11-20", "2026-11-02"), own, [other], repo_settings()
    )
    assert judged.evidence == "supports"


def test_date_edit_against_the_prescription_contradicts() -> None:
    own = reading("r", field("r", "treatment_date", "2026-11-20"))
    other = reading("p", field("p", "treatment_date", "2026-11-20"))
    judged = judge_edit(
        edit("treatment_date", "2026-11-01", "2026-11-20"), own, [other], repo_settings()
    )
    assert judged.evidence == "contradicts"


def test_total_edit_that_makes_subtotal_plus_vat_add_up_supports() -> None:
    own = reading(
        "r",
        field("r", "subtotal", "15000"),
        field("r", "vat_total", "2250"),
        field("r", "total", "71250"),
    )
    judged = judge_edit(edit("total", "17250", "71250"), own, [], repo_settings())
    assert judged.evidence == "supports" and "add up" in judged.evidence_note


def test_total_edit_that_breaks_the_arithmetic_contradicts() -> None:
    own = reading(
        "r",
        field("r", "subtotal", "15000"),
        field("r", "vat_total", "2250"),
        field("r", "total", "17250"),
    )
    judged = judge_edit(edit("total", "27250", "17250"), own, [], repo_settings())
    assert judged.evidence == "contradicts"


def test_total_edit_with_no_qr_no_other_document_no_arithmetic_is_none() -> None:
    own = reading("r", field("r", "total", "17250"))
    judged = judge_edit(edit("total", "27250", "17250"), own, [], repo_settings())
    assert judged.evidence == "none"


def test_agreeing_evidence_beats_disagreeing_evidence() -> None:
    own = reading("r", field("r", "treatment_date", "2026-11-02"))
    agrees = reading("p", field("p", "treatment_date", "2026-11-20"))
    disagrees = reading("m", field("m", "treatment_date", "2026-11-03"))
    judged = judge_edit(
        edit("treatment_date", "2026-11-20", "2026-11-02"),
        own,
        [disagrees, agrees],
        repo_settings(),
    )
    assert judged.evidence == "supports"


def raw(*fields: ExtractedField) -> ReaderOutput:
    return ReaderOutput(fields=list(fields), line_items=[], qr_payloads=[])


def test_apply_edits_uses_a_supported_value_as_member_typed() -> None:
    supported = edit("total", "17250", "71250").model_copy(update={"evidence": "supports"})
    out = apply_edits("r", raw(field("r", "total", "71250")), [supported], repo_settings())
    totals = [f for f in out.fields if f.name == "total"]
    assert [(f.value, f.source) for f in totals] == [("17250", "member_typed")]
    assert totals[0].confidence == repo_settings().decision.passed_check_confidence


def test_apply_edits_keeps_the_read_value_for_a_contradicting_edit() -> None:
    against = edit("total", "71250", "17250").model_copy(update={"evidence": "contradicts"})
    out = apply_edits("r", raw(field("r", "total", "17250")), [against], repo_settings())
    assert [(f.value, f.source) for f in out.fields] == [("17250", "ocr")]


def test_unbacked_edit_on_a_rule_field_is_not_applied() -> None:
    unbacked = edit("total", "27250", "17250")
    out = apply_edits("r", raw(field("r", "total", "17250")), [unbacked], repo_settings())
    assert [f.source for f in out.fields] == ["ocr"]


def test_unbacked_provider_name_edit_is_applied_with_capped_confidence() -> None:
    unbacked = edit("provider_name", "Al Noor Clinic", "Al Nour Clnic")
    out = apply_edits(
        "r", raw(field("r", "provider_name", "Al Nour Clnic")), [unbacked], repo_settings()
    )
    assert [(f.value, f.source, f.confidence) for f in out.fields] == [
        ("Al Noor Clinic", "member_typed", repo_settings().documents.unbacked_edit_confidence)
    ]


def test_an_edit_for_another_document_is_ignored() -> None:
    other_doc = edit("total", "17250", "71250", document_id="x").model_copy(
        update={"evidence": "supports"}
    )
    out = apply_edits("r", raw(field("r", "total", "71250")), [other_doc], repo_settings())
    assert [f.value for f in out.fields] == ["71250"]


def test_a_supported_edit_adds_a_field_the_reader_missed() -> None:
    supported = edit("total", "17250").model_copy(update={"evidence": "supports"})
    out = apply_edits("r", raw(), [supported], repo_settings())
    assert [(f.document_id, f.value, f.source) for f in out.fields] == [
        ("r", "17250", "member_typed")
    ]
