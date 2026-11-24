from reimbursement_council.web.check_form import form_value, parse_edits

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
