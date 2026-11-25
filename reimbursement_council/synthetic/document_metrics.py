"""Score how a run handled the documents: their types, the missing ones, and the cross checks.

Each metric is a share from 0 to 1, with the size of its group next to it (name_count), so a
0.0 from an empty group is never mistaken for a bad result. A billing document read as
"receipt" when the truth is "invoice" counts as wrong: the metric is strict on purpose.
"""

from collections.abc import Sequence

from reimbursement_council.synthetic.metrics import RunRow

MISMATCH_DEFECTS = frozenset({"patient_name_mismatch", "date_mismatch"})


def _with_count(name: str, hits: int, group: int) -> dict[str, float]:
    return {name: round(hits / group, 4) if group else 0.0, f"{name}_count": group}


def document_metrics(rows: Sequence[RunRow]) -> dict[str, float]:
    kinds = [
        (r.kinds_read.get(doc_id), kind) for r in rows for doc_id, kind in r.kinds_true.items()
    ]
    missing = [(r, g) for r in rows for g in r.needs_missing]
    flagged = [(r, g) for r in rows for g in r.needs_flagged]
    expected = [r for r in rows if r.cross_check_expected]
    clean = [r for r in rows if not r.cross_check_expected]
    laned = [r for r in rows if r.expected_lane is not None]
    return (
        _with_count("document_kind_accuracy", sum(read == true for read, true in kinds), len(kinds))
        | _with_count(
            "missing_document_recall", sum(g in r.needs_flagged for r, g in missing), len(missing)
        )
        | _with_count(
            "missing_document_precision",
            sum(g in r.needs_missing for r, g in flagged),
            len(flagged),
        )
        | _with_count(
            "cross_check_catch_rate", sum(r.cross_check_failed for r in expected), len(expected)
        )
        | _with_count(
            "cross_check_false_alarm_rate", sum(r.cross_check_failed for r in clean), len(clean)
        )
        | _with_count(
            "expected_lane_match", sum(r.lane == r.expected_lane for r in laned), len(laned)
        )
    )
