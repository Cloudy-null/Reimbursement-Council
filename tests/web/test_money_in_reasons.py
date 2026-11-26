"""Money the member typed is shown to the reviewer in riyals, not halalas."""

from reimbursement_council.core.decision.document_requests import shown_value
from reimbursement_council.web.review_view import why_reasons


def test_money_fields_show_riyals_and_other_fields_stay_as_they_are() -> None:
    assert shown_value("total", "99900") == "999.00 SAR"
    assert shown_value("treatment_date", "2026-11-23") == "2026-11-23"


def test_the_why_box_shows_the_typed_total_in_riyals() -> None:
    export = {
        "member_edits": [
            {
                "field": "total",
                "typed_value": "99900",
                "read_value": "17250",
                "evidence": "contradicts",
            }
        ]
    }
    reasons = why_reasons(export, "")
    assert any("999.00 SAR" in r and "172.50 SAR" in r for r in reasons), reasons
    assert not any("99900" in r for r in reasons)
