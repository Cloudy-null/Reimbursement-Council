"""Approval and problem precision and recall, for the numbers page. Pure.

- Approval precision: of claims auto approved, the share that should be paid at that amount.
- Payable recall: of claims that should be paid, the share auto approved.
- Problem precision: of claims we flagged (asked the member, sent to a person, or rejected),
  the share that really had a problem (a defect in the generator's truth).
- Problem recall: of claims that really had a problem, the share we flagged before paying.
"""

from collections.abc import Sequence

from reimbursement_council.synthetic.metrics import RunRow, paid_right

FLAGGED = frozenset({"self_fix", "human_review", "auto_reject"})


def _share(hits: int, total: int) -> dict[str, float | int | None]:
    return {"value": None if total == 0 else round(hits / total, 4), "hits": hits, "n": total}


def flag_metrics(
    rows: Sequence[RunRow], tolerance: int
) -> dict[str, dict[str, float | int | None]]:
    approved = [r for r in rows if r.lane == "auto_approve"]
    payable = [r for r in rows if r.should_pay]
    flagged = [r for r in rows if r.lane in FLAGGED]
    problems = [r for r in rows if r.defects]
    return {
        "approval_precision": _share(
            sum(paid_right(r, tolerance) for r in approved), len(approved)
        ),
        "payable_recall": _share(sum(r.lane == "auto_approve" for r in payable), len(payable)),
        "problem_precision": _share(sum(bool(r.defects) for r in flagged), len(flagged)),
        "problem_recall": _share(sum(r.lane in FLAGGED for r in problems), len(problems)),
    }
