from datetime import date

from reimbursement_council.core.models.claim import LineItem
from reimbursement_council.synthetic.optical_claims import make_optical_set
from reimbursement_council.synthetic.optical_scenarios import SCENARIOS
from reimbursement_council.synthetic.sheet_cases import SET_LABEL, SheetCase, truth_payout
from tests.factories import repo_settings


def _by_scenario(seed: int = 1) -> dict[str, SheetCase]:
    return {case.scenario: case for case in make_optical_set(seed, repo_settings()).cases}


def test_one_claim_per_scenario_and_same_seed_same_set() -> None:
    settings = repo_settings()
    first = make_optical_set(3, settings)
    assert first == make_optical_set(3, settings)
    assert first != make_optical_set(4, settings)
    assert [c.scenario for c in first.cases] == [s.name for s in SCENARIOS]
    assert 18 <= len(first.cases) <= 22
    assert first.label == SET_LABEL == "real-derived synthetic"
    assert len({c.claim.member_id for c in first.cases}) == len(first.cases)


def test_frame_sub_limit_payouts() -> None:
    cases = _by_scenario()
    # frames 1,600 + lenses 150, 600 SAR of frames used: 400 + 150 = 550, share 20% = 110
    # capped at 100, pays 450 SAR
    assert cases["frames_partly_used"].truth.correct_payout == 45000
    # frames free, 300 + 150 = 450, share 90 (under the cap), pays 360; VAT not paid
    assert cases["frames_free_share_under_cap"].truth.correct_payout == 36000
    # frames free, 900 + 500 = 1,400, share 280 capped at 100, pays 1,300
    assert cases["frames_free_share_at_cap"].truth.correct_payout == 130000
    # frames used up: only lenses 300, share 60, pays 240
    assert cases["frames_fully_used"].truth.correct_payout == 24000
    # 500 of frames left: 500 + 400 = 900, share 100, pays 800 (15% VAT left out)
    assert cases["frames_partly_used_vat"].truth.correct_payout == 80000


def test_history_carries_the_frame_usage() -> None:
    optical = make_optical_set(1, repo_settings())
    used = {
        case.scenario: optical.reference.history(case.claim.member_id).limits_used
        for case in optical.cases
    }
    assert used["frames_partly_used"] == {"optical_frames": 60000}
    assert used["frames_fully_used"] == {"optical_frames": 100000}
    assert used["frames_free_share_at_cap"] == {}


def test_every_payout_matches_calculate_payout() -> None:
    settings = repo_settings()
    optical = make_optical_set(2, settings)
    for case in optical.cases:
        rows = case.fields["items"]
        assert isinstance(rows, list)
        items = [
            LineItem(
                description="x",
                service_code=str(row["service_code"]),
                quantity=int(row["quantity"]),
                unit_price=int(row["amount"]),
                amount=int(row["amount"]),
                confidence=1.0,
            )
            for row in rows
        ]
        expected = truth_payout(
            items,
            int(str(case.fields["vat_total"])),
            optical.reference.policy(case.claim.policy_id),
            optical.reference.history(case.claim.member_id),
            settings,
        )
        assert case.truth.correct_payout == (expected if case.truth.should_pay else 0)


def test_vat_is_never_paid() -> None:
    lenses = _by_scenario()["lenses_only"]
    assert lenses.fields["vat_total"] == "6750"
    assert lenses.truth.correct_payout == 36000  # 450 less a 90 share, no VAT


def test_missing_document_scenarios() -> None:
    cases = _by_scenario()
    for name in ("missing_eye_test_1", "missing_eye_test_2"):
        case = cases[name]
        assert case.truth.defects == ["missing_eye_test"]
        assert case.truth.expected_lane == "self_fix"
        assert case.truth.needs_missing == [["prescription"]]
        assert "الوصفة الطبية" not in case.documents[0].sheet.text()
        assert len(case.documents) == 1
        assert case.fix is not None and case.fix.kind == "prescription"
    for name in ("credit_without_proof_1", "credit_without_proof_2"):
        case = cases[name]
        assert case.truth.defects == ["missing_payment_proof"]
        assert case.truth.expected_lane == "self_fix"
        assert "آجل" in case.documents[0].sheet.text()
        assert case.fix is not None and case.fix.kind == "receipt"


def test_invalid_invoice_and_late_scenarios() -> None:
    cases = _by_scenario()
    for name in ("invoice_number_missing", "vat_number_missing"):
        case = cases[name]
        assert case.truth.defects == ["invalid_invoice"]
        assert case.truth.expected_lane == "self_fix"
        fix = case.fix
        assert fix is not None and fix.replace_document_id == case.documents[0].document_id
    assert "رقم الفاتورة" not in cases["invoice_number_missing"].documents[0].sheet.text()
    assert "الرقم الضريبي" not in cases["vat_number_missing"].documents[0].sheet.text()
    for name in ("late_1", "late_2"):
        case = cases[name]
        assert case.truth.defects == ["late"] and not case.truth.should_pay
        assert case.truth.correct_payout == 0 and case.truth.expected_lane == "auto_reject"
        treated = date.fromisoformat(str(case.fields["treatment_date"]))
        assert (case.claim.submitted_at.date() - treated).days > 90


def test_clean_scenarios_have_no_defect() -> None:
    cases = _by_scenario()
    for name in (
        "credit_with_proof",
        "tabby_no_proof",
        "tabby_no_proof_vat",
        "eye_test_separate_document",
        "cash_paid",
    ):
        truth = cases[name].truth
        assert truth.defects == [] and truth.expected_lane is None and truth.needs_missing == []
        assert truth.should_pay and truth.correct_payout > 0
    assert [d.kind for d in cases["credit_with_proof"].documents] == ["invoice", "receipt"]
    assert "تابي" in cases["tabby_no_proof"].documents[0].sheet.text()
    separate = cases["eye_test_separate_document"]
    assert [d.kind for d in separate.documents] == ["invoice", "prescription"]
    assert separate.documents[1].file_name.endswith("-1.png")
    assert set(separate.truth.document_kinds.values()) == {"invoice", "prescription"}
