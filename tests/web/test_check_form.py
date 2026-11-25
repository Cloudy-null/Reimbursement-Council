from datetime import UTC, datetime

from reimbursement_council.core.models.claim import Document
from reimbursement_council.web.check_form import (
    chosen_categories,
    chosen_kinds,
    form_value,
    parse_edits,
)


def document(
    document_id: str, kind: str = "prescription", source: str = "detected", detected: str = ""
) -> Document:
    return Document(
        document_id=document_id,
        claim_id="c",
        kind=kind,  # type: ignore[arg-type]
        kind_source=source,  # type: ignore[arg-type]
        detected_kind=detected or None,  # type: ignore[arg-type]
        file_path="x.png",
        image_hash=None,
        uploaded_at=datetime(2026, 11, 20, tzinfo=UTC),
    )


READ = {"total": "17250", "treatment_date": "2026-11-20", "patient_name": "Sara Ahmed"}


def test_form_shows_money_in_sar() -> None:
    assert form_value("total", "17250") == "172.50"
    assert form_value("patient_name", "Sara Ahmed") == "Sara Ahmed"
    assert form_value("total", None) == ""


def test_unchanged_or_empty_fields_make_no_edit() -> None:
    form = {"field_total": "172.50", "field_patient_name": " Sara   Ahmed ", "field_subtotal": ""}
    assert parse_edits(form, "d1", READ) == ([], {})  # type: ignore[arg-type]


def test_changed_values_become_edits_in_stored_form() -> None:
    form = {"field_total": "١٨٠٫٠٠", "field_treatment_date": "2026-11-21"}
    edits, errors = parse_edits(form, "d1", READ)  # type: ignore[arg-type]
    assert errors == {}
    assert [(e.field, e.read_value, e.typed_value) for e in edits] == [
        ("treatment_date", "2026-11-20", "2026-11-21"),
        ("total", "17250", "18000"),
    ]


def test_bad_values_are_errors_not_edits() -> None:
    form = {"field_total": "12,50x", "field_treatment_date": "20/11", "field_vat_number": "3001"}
    edits, errors = parse_edits(form, "d1", READ)  # type: ignore[arg-type]
    assert edits == []
    assert errors == {
        "total": "error_money",
        "treatment_date": "error_date",
        "vat_number": "error_vat",
    }


def test_an_unchanged_reader_value_that_is_not_valid_does_not_block() -> None:
    # OCR can read 31/11/2026; the member did not touch it, so it must not stop the submit.
    read = {"treatment_date": "2026-11-31", "vat_number": "3001"}
    form = {"field_treatment_date": "2026-11-31", "field_vat_number": "3001"}
    assert parse_edits(form, "d1", read) == ([], {})  # type: ignore[arg-type]


def test_kind_goes_back_to_detected_when_the_member_picks_the_detected_kind() -> None:
    member_set = document("d2", kind="medical_report", source="member", detected="prescription")
    (back,) = chosen_kinds([member_set], {"kind_d2": "prescription"})
    assert (back.kind, back.kind_source) == ("prescription", "detected")
    (changed,) = chosen_kinds([document("d2", detected="prescription")], {"kind_d2": "other"})
    assert (changed.kind, changed.kind_source) == ("other", "member")
    (kept,) = chosen_kinds([member_set], {})
    assert kept == member_set


def test_category_is_cleared_when_auto_or_the_detected_one_is_picked() -> None:
    valid = ["outpatient", "pharmacy", "dental"]
    assert chosen_categories("", valid, ["pharmacy"]) == []
    assert chosen_categories("pharmacy", valid, ["pharmacy"]) == []
    assert chosen_categories("dental", valid, ["pharmacy"]) == ["dental"]
    assert chosen_categories("made-up", valid, ["pharmacy"]) == []
