import random
from datetime import datetime

from reimbursement_council.adapters.dental_drawing import draw_dental_invoice
from reimbursement_council.synthetic.dental_claims import (
    dental_sheet,
    make_dental_invoice,
    make_dental_set,
)
from reimbursement_council.synthetic.receipt_content import PersonName
from tests.factories import repo_settings

PATIENT = PersonName(en="Test Person", ar="شخص تجريبي")


def test_tooth_number_line_is_printed_only_when_known() -> None:
    with_tooth = make_dental_invoice(
        random.Random(1), [("DENT-FILL", 35000)], 0.15, PATIENT, datetime(2026, 9, 3, 11, 0), 14
    )
    without = with_tooth.model_copy(update={"tooth": None})
    assert "رقم السن 14 / Tooth 14" in dental_sheet(with_tooth).text()
    assert "رقم السن" not in dental_sheet(without).text()
    assert "حشوة" in dental_sheet(with_tooth).text()
    assert draw_dental_invoice(with_tooth).png == draw_dental_invoice(with_tooth).png


def test_half_the_claims_miss_the_tooth_number() -> None:
    settings = repo_settings()
    dental = make_dental_set(1, settings)
    assert dental == make_dental_set(1, settings)
    assert len(dental.cases) == 6
    missing = [c for c in dental.cases if c.truth.defects == ["missing_tooth_number"]]
    present = [c for c in dental.cases if not c.truth.defects]
    assert len(missing) == len(present) == 3
    for case in missing:
        assert case.truth.expected_lane == "self_fix" and case.truth.should_pay
        assert "رقم السن" not in case.documents[0].sheet.text()
        assert case.fix is not None and "رقم السن" in case.fix.sheet.text()
        assert case.fix.replace_document_id == case.documents[0].document_id
    for case in present:
        assert case.truth.expected_lane is None and case.fix is None
        assert "Tooth" in case.documents[0].sheet.text()


def test_dental_payouts_follow_the_policy() -> None:
    by_scenario = make_dental_set(1, repo_settings()).cases
    # a 350 SAR filling: 20% share is 70 (under the 100 cap), pays 280; VAT not paid
    assert by_scenario[0].truth.correct_payout == 28000
    # filling 400 + cleaning 250 = 650, share 130 capped at 100, pays 550
    assert by_scenario[2].truth.correct_payout == 55000
