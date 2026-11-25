"""What a one-tap "yes, this date is right" may do. Pure logic, no I/O.

- Another document shows the same date: the date counts, no person needed.
- Another document shows a different date: a person checks it.
- Nothing else shows a date: the date counts, unless the claim is near the claim window limit
  (within the margin from config, or past it, or the date is after the claim was sent). Then a
  member's tap alone would decide a hard rule, so a person checks it.
"""

from datetime import date
from typing import Literal

from reimbursement_council.core.models.common import EditEvidence

ConfirmVerdict = Literal["use_date", "human_review"]


def confirm_verdict(
    evidence: EditEvidence,
    treated: date,
    submitted: date,
    window_days: int,
    margin_days: int,
) -> tuple[ConfirmVerdict, str]:
    """The verdict on a confirmed date, and a plain reason for the record."""
    if evidence == "contradicts":
        return "human_review", "another document shows a different date"
    if evidence == "supports":
        return "use_date", "another document shows the same date"
    days = (submitted - treated).days
    if days < 0:
        return "human_review", "the confirmed date is after the claim was sent"
    if days > window_days - margin_days:
        return (
            "human_review",
            f"the claim was sent {days} days after the treatment, within {margin_days} days of "
            f"the {window_days} day limit or past it",
        )
    return "use_date", f"the claim was sent {days} days after the treatment, well inside the limit"
