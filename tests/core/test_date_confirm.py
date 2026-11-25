from datetime import date

import pytest

from reimbursement_council.core.date_confirm import confirm_verdict

SENT = date(2026, 11, 25)


@pytest.mark.parametrize(
    ("evidence", "treated", "verdict"),
    [
        ("supports", date(2026, 8, 30), "use_date"),  # 87 days, but another document agrees
        ("contradicts", date(2026, 11, 20), "human_review"),
        ("none", date(2026, 11, 20), "use_date"),  # 5 days: well inside 90
        ("none", date(2026, 9, 3), "use_date"),  # 83 days: exactly at 90 - 7
        ("none", date(2026, 9, 2), "human_review"),  # 84 days: within 7 of the limit
        ("none", date(2026, 7, 1), "human_review"),  # past the limit: a tap never rejects
        ("none", date(2026, 11, 26), "human_review"),  # after the claim was sent
    ],
)
def test_confirm_verdict(evidence: str, treated: date, verdict: str) -> None:
    got, reason = confirm_verdict(evidence, treated, SENT, window_days=90, margin_days=7)  # type: ignore[arg-type]
    assert got == verdict
    assert reason
