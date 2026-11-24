"""Reading a whole document set: kinds, primary billing document, edits, needs, cross checks."""

from datetime import UTC, date, datetime

import pytest

from reimbursement_council.core.models.claim import (
    Claim,
    Document,
    ExtractedField,
    FieldEdit,
    LineItem,
    ReaderOutput,
)
from reimbursement_council.core.models.common import DocumentKind, FieldName, KindSource
from reimbursement_council.core.models.reference import Member
from reimbursement_council.pipeline.document_set import read_document_set
from tests.factories import repo_settings, settings_with
from tests.fixtures.build_fixtures import qr

SARA = Member(
    member_id="m1",
    display_name="Sara Ahmed",
    name_ar="سارة أحمد",
    date_joined=date(2023, 1, 1),
    policy_id="p",
)
WHEN = datetime(2026, 11, 20, 9, tzinfo=UTC)


def doc(
    document_id: str,
    kind: DocumentKind = "other",
    image_hash: str | None = None,
    kind_source: KindSource = "detected",
) -> Document:
    return Document(
        document_id=document_id,
        claim_id="c",
        kind=kind,
        file_path=f"{document_id}.png",
        image_hash=image_hash,
        uploaded_at=WHEN,
        kind_source=kind_source,
    )


def field(document_id: str, name: FieldName, value: str) -> ExtractedField:
    return ExtractedField(
        document_id=document_id,
        name=name,
        value=value,
        original_text=value,
        source="ocr",
        confidence=0.95,
    )


def bill(
    document_id: str,
    code: str = "MED-IBU",
    total: int = 4600,
    with_qr: bool = True,
    text: str = "Green Leaf Pharmacy",
) -> ReaderOutput:
    subtotal = total * 100 // 115
    vat = total - subtotal
    return ReaderOutput(
        fields=[
            field(document_id, "subtotal", str(subtotal)),
            field(document_id, "vat_total", str(vat)),
            field(document_id, "total", str(total)),
            field(document_id, "treatment_date", "2026-11-15"),
            field(document_id, "patient_name", "Sara Ahmed"),
        ],
        line_items=[
            LineItem(
                description="item",
                service_code=code,
                quantity=1,
                unit_price=subtotal,
                amount=subtotal,
                confidence=0.95,
            )
        ],
        qr_payloads=[qr("2026-11-15T10:30:00Z", total, vat)] if with_qr else [],
        text_lines=[text],
    )


def clinical(document_id: str, title: str, patient: str = "سارة أحمد") -> ReaderOutput:
    return ReaderOutput(
        fields=[
            field(document_id, "patient_name", patient),
            field(document_id, "treatment_date", "2026-11-15"),
        ],
        line_items=[],
        qr_payloads=[],
        text_lines=[title, "Dr. Huda"],
    )


def claim(*documents: Document, **changes: object) -> Claim:
    base = Claim(
        claim_id="c",
        member_id="m1",
        patient_member_id="m1",
        policy_id="p",
        submitted_at=WHEN,
        status="submitted",
        documents=list(documents),
        retries_used=0,
    )
    return base.model_copy(update=changes)


def never_read(document: Document) -> object:
    raise AssertionError(f"{document.document_id} was read again")


def read(c: Claim, readings: dict[str, ReaderOutput], **settings_changes: object):  # type: ignore[no-untyped-def]
    settings = settings_with(**settings_changes) if settings_changes else repo_settings()
    return read_document_set(c, SARA, settings, never_read, readings)  # type: ignore[arg-type]


def test_reads_every_document_and_detects_kinds() -> None:
    result = read(claim(doc("r"), doc("p")), {"r": bill("r"), "p": clinical("p", "وصفة طبية")})
    assert {d.document_id: d.kind for d in result.documents} == {
        "r": "receipt",
        "p": "prescription",
    }
    assert set(result.readings) == {"r", "p"}
    assert result.categories == ["pharmacy"]
    assert all(need.satisfied for need in result.needs)


def test_same_file_twice_is_dropped_with_a_note() -> None:
    result = read(
        claim(doc("r", image_hash="h1"), doc("r2", image_hash="h1")),
        {"r": bill("r"), "r2": bill("r2")},
    )
    assert [d.document_id for d in result.documents] == ["r"]
    assert any("same file" in note for note in result.notes)


def test_primary_is_the_billing_document_with_a_qr() -> None:
    readings = {
        "i": bill("i", with_qr=False, text="Tax Invoice"),
        "r": bill("r", with_qr=True),
    }
    assert read(claim(doc("i"), doc("r")), readings).primary_id == "r"


def test_without_a_qr_the_invoice_is_primary() -> None:
    readings = {
        "r": bill("r", with_qr=False, text="Receipt"),
        "i": bill("i", with_qr=False, text="Tax Invoice"),
    }
    assert read(claim(doc("r"), doc("i")), readings).primary_id == "i"


def test_member_set_kind_is_kept_and_the_detected_kind_remembered() -> None:
    result = read(
        claim(doc("r"), doc("p", kind="prescription", kind_source="member")),
        {"r": bill("r"), "p": clinical("p", "Medical Report")},
    )
    prescription = next(d for d in result.documents if d.document_id == "p")
    assert prescription.kind == "prescription" and prescription.detected_kind == "medical_report"


def test_kind_change_that_hides_a_missing_prescription_is_a_member_edit() -> None:
    result = read(
        claim(doc("r"), doc("m", kind="prescription", kind_source="member")),
        {"r": bill("r"), "m": clinical("m", "Medical Report")},
    )
    assert [r.rule for r in result.edit_rule_results] == ["member_edit"]
    assert result.edit_rule_results[0].outcome == "not_sure"


def test_category_change_that_drops_the_prescription_is_a_member_edit() -> None:
    result = read(claim(doc("r"), claim_categories=["lab"]), {"r": bill("r")})
    assert result.categories == ["lab"]
    assert all(need.satisfied for need in result.needs)
    assert [r.rule for r in result.edit_rule_results] == ["member_edit"]


def test_category_change_that_adds_a_requirement_is_fine() -> None:
    result = read(
        claim(doc("r"), doc("p"), claim_categories=["outpatient", "pharmacy"]),
        {"r": bill("r"), "p": clinical("p", "وصفة طبية")},
    )
    assert result.edit_rule_results == []
    assert [n.group for n in result.needs if not n.satisfied] == [["medical_report"]]


def test_stored_readings_are_used_instead_of_reading_again() -> None:
    result = read(claim(doc("r")), {"r": bill("r")})  # never_read raises if called
    assert result.primary_id == "r"


def test_supported_edit_is_used_and_contradicting_edit_is_flagged() -> None:
    supported = FieldEdit(document_id="r", field="total", read_value="9999", typed_value="4600")
    result = read(claim(doc("r"), edits=[supported]), {"r": bill("r", total=4600)})
    assert result.readings["r"].best("total").value == "4600"  # type: ignore[union-attr]
    assert result.edits[0].evidence == "supports" and result.edit_rule_results == []

    against = FieldEdit(document_id="r", field="total", read_value="4600", typed_value="9900")
    result = read(claim(doc("r"), edits=[against]), {"r": bill("r", total=4600)})
    assert result.readings["r"].money("total") == 4600
    assert result.edits[0].evidence == "contradicts"
    assert [r.rule for r in result.edit_rule_results] == ["member_edit"]


def test_other_patient_on_the_prescription_fails_the_cross_check() -> None:
    result = read(
        claim(doc("r"), doc("p")),
        {"r": bill("r"), "p": clinical("p", "وصفة طبية", patient="عمر خالد")},
    )
    patient = next(c for c in result.cross_checks if c.name == "patient_matches_account")
    assert patient.passed is False


def test_cross_checks_off_by_switch() -> None:
    result = read(
        claim(doc("r"), doc("p")),
        {"r": bill("r"), "p": clinical("p", "وصفة طبية")},
        cross_checks_enabled=False,
    )
    assert result.cross_checks == []


@pytest.mark.parametrize("second_total, conflict", [(4600, False), (5000, True)])
def test_two_billing_documents_conflict_only_when_totals_differ(
    second_total: int, conflict: bool
) -> None:
    readings = {
        "r": bill("r"),
        "i": bill("i", total=second_total, with_qr=False, text="Tax Invoice"),
    }
    assert read(claim(doc("r"), doc("i")), readings).billing_documents_differ is conflict


EMPTY = ReaderOutput(fields=[], line_items=[], qr_payloads=[])


def test_member_kind_on_an_unreadable_photo_is_a_member_edit() -> None:  # review C1
    result = read(
        claim(doc("r"), doc("p", kind="prescription", kind_source="member")),
        {"r": bill("r"), "p": EMPTY},
    )
    prescription = next(d for d in result.documents if d.document_id == "p")
    assert prescription.detected_kind == "other"
    assert [r.rule for r in result.edit_rule_results] == ["member_edit"]


def test_an_unreadable_photo_is_other() -> None:  # review C1, Review Focus 1
    result = read(claim(doc("r"), doc("x", kind="receipt")), {"r": bill("r"), "x": EMPTY})
    assert next(d.kind for d in result.documents if d.document_id == "x") == "other"


def test_money_on_a_non_billing_document_does_not_back_an_edit() -> None:  # review I1
    note = ReaderOutput(
        fields=[field("n", "total", "9900")], line_items=[], qr_payloads=[], text_lines=["note"]
    )
    raised = FieldEdit(document_id="r", field="total", read_value="4600", typed_value="9900")
    result = read(
        claim(doc("r"), doc("n"), edits=[raised]),
        {"r": bill("r", total=4600, with_qr=False, text="Receipt"), "n": note},
    )
    assert result.edits[0].evidence != "supports"
    assert result.readings["r"].money("total") == 4600
    assert result.readings["n"].best("total") is None


def test_billing_documents_with_different_vat_numbers_differ() -> None:  # review I2
    other_shop = bill("i", with_qr=False, text="Tax Invoice")
    other_shop = other_shop.model_copy(
        update={"fields": [*other_shop.fields, field("i", "vat_number", "300765432100003")]}
    )
    first = bill("r")
    first = first.model_copy(
        update={"fields": [*first.fields, field("r", "vat_number", "300000000000003")]}
    )
    result = read(claim(doc("r"), doc("i")), {"r": first, "i": other_shop})
    assert result.billing_documents_differ is True


def test_a_document_that_cannot_be_read_does_not_stop_the_claim() -> None:  # review I3
    def reader_for(document: Document) -> object:
        raise ValueError("no reader for file type '.pdf'")

    result = read_document_set(
        claim(doc("r"), doc("x")),
        SARA,
        repo_settings(),
        reader_for,
        {"r": bill("r")},  # type: ignore[arg-type]
    )
    assert next(d.kind for d in result.documents if d.document_id == "x") == "other"
    assert any("could not be read" in note for note in result.notes)


def test_read_value_comes_from_the_reading_not_the_form() -> None:  # review M2
    edit = FieldEdit(document_id="r", field="total", read_value="1", typed_value="9900")
    result = read(claim(doc("r"), edits=[edit]), {"r": bill("r", total=4600)})
    assert result.edits[0].read_value == "4600"
