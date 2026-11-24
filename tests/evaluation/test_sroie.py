"""Real receipts (SROIE): read the true values from a key file and score a reading."""

from reimbursement_council.core.models.claim import ExtractedField, ExtractionResult
from reimbursement_council.evaluation.sroie import compare_real, parse_sroie_key, summarize_real


def reading(**values: str) -> ExtractionResult:
    fields = [
        ExtractedField(
            document_id="d",
            name=name,  # type: ignore[arg-type]
            value=value,
            original_text=value,
            source="ocr",
            confidence=0.9,
        )
        for name, value in values.items()
    ]
    return ExtractionResult(document_id="d", fields=fields, line_items=[], checks=[])


def test_key_values_become_halalas_and_iso_dates() -> None:
    truth = parse_sroie_key(
        {"company": "BOOK TA .K SDN BHD", "date": "25/12/2018", "total": "9.00"}
    )
    assert (truth.company, truth.date, truth.total) == ("BOOK TA .K SDN BHD", "2018-12-25", 900)


def test_many_date_forms_are_understood_and_odd_ones_are_left_out() -> None:
    forms = {
        "25/12/18": "2018-12-25",
        "25-12-2018": "2018-12-25",
        "2018-12-25": "2018-12-25",
        "25.12.2018": "2018-12-25",
        "25 DEC 2018": "2018-12-25",
        "DEC 25, 2018": "2018-12-25",
        "sometime": None,
    }
    for text, expected in forms.items():
        assert parse_sroie_key({"company": "x", "date": text, "total": "1.00"}).date == expected
    assert (
        parse_sroie_key({"company": "x", "date": "1/1/2018", "total": "RM 1,234.50"}).total
        == 123450
    )


def test_compare_marks_each_field_and_leaves_unknown_truth_out() -> None:
    truth = parse_sroie_key(
        {"company": "SANYU STATIONERY SHOP", "date": "28/03/2018", "total": "6.50"}
    )
    row = compare_real(
        truth,
        reading(provider_name="SANYU STATIONERY SHOP", treatment_date="2018-03-28", total="650"),
        0.85,
    )
    assert row == {"provider_name": True, "treatment_date": True, "total": True}
    unknown = parse_sroie_key({"company": "x", "date": "?", "total": "1.00"})
    assert compare_real(unknown, reading(), 0.85) == {
        "provider_name": False,
        "treatment_date": None,
        "total": False,
    }


def test_summary_counts_only_known_truth() -> None:
    rows = [
        {"provider_name": True, "treatment_date": None, "total": True},
        {"provider_name": False, "treatment_date": True, "total": False},
    ]
    summary = summarize_real(rows)
    assert summary["total"] == 0.5 and summary["treatment_date"] == 1.0
    assert summary["treatment_date_count"] == 1 and summary["receipts"] == 2
