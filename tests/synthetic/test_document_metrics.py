"""Task 11: run-set scores document types, missing documents and cross checks."""

from typing import Any

import pytest

from reimbursement_council.synthetic.document_metrics import document_metrics
from reimbursement_council.synthetic.metrics import RunRow


def row(**changes: Any) -> RunRow:
    base: dict[str, Any] = {
        "name": "c",
        "lane": "auto_approve",
        "outcome": "complete",
        "payout_calculated": 100,
        "p_good": 0.9,
        "combined_score": 0.9,
        "should_pay": True,
        "correct_payout": 100,
        "defects": [],
        "hard_rule_failed": False,
        "damage": "none",
    }
    return RunRow(**(base | changes))


def test_document_kind_accuracy_counts_every_document() -> None:
    rows = [
        row(
            kinds_true={"a": "invoice", "b": "prescription"},
            kinds_read={"a": "invoice", "b": "other"},
        ),
        row(kinds_true={"c": "invoice"}, kinds_read={"c": "invoice"}),
    ]
    scores = document_metrics(rows)
    assert scores["document_kind_accuracy"] == pytest.approx(2 / 3, abs=1e-4)
    assert scores["document_kind_accuracy_count"] == 3


def test_missing_document_recall_and_precision() -> None:
    rows = [
        row(needs_missing=[["prescription"]], needs_flagged=[["prescription"]]),
        row(needs_missing=[["medical_report"]], needs_flagged=[]),
        row(needs_missing=[], needs_flagged=[["invoice", "receipt"]]),
    ]
    scores = document_metrics(rows)
    assert scores["missing_document_recall"] == 0.5
    assert scores["missing_document_recall_count"] == 2
    assert scores["missing_document_precision"] == 0.5
    assert scores["missing_document_precision_count"] == 2


def test_cross_check_catch_and_false_alarm_rates() -> None:
    rows = [
        row(cross_check_expected=True, cross_check_failed=True),
        row(cross_check_expected=True, cross_check_failed=False),
        row(cross_check_expected=False, cross_check_failed=True),
        row(cross_check_expected=False, cross_check_failed=False),
        row(cross_check_expected=False, cross_check_failed=False),
        row(cross_check_expected=False, cross_check_failed=False),
    ]
    scores = document_metrics(rows)
    assert scores["cross_check_catch_rate"] == 0.5
    assert scores["cross_check_catch_rate_count"] == 2
    assert scores["cross_check_false_alarm_rate"] == 0.25
    assert scores["cross_check_false_alarm_rate_count"] == 4


def test_expected_lane_match_uses_only_rows_with_an_expected_lane() -> None:
    rows = [
        row(expected_lane="self_fix", lane="self_fix"),
        row(expected_lane="human_review", lane="self_fix"),
        row(expected_lane=None, lane="auto_reject"),
    ]
    scores = document_metrics(rows)
    assert scores["expected_lane_match"] == 0.5 and scores["expected_lane_match_count"] == 2


def test_empty_groups_give_zero_with_a_zero_count() -> None:
    scores = document_metrics([row()])
    for name in (
        "document_kind_accuracy",
        "missing_document_recall",
        "missing_document_precision",
        "cross_check_catch_rate",
        "expected_lane_match",
    ):
        assert scores[name] == 0.0 and scores[f"{name}_count"] == 0
    assert scores["cross_check_false_alarm_rate_count"] == 1


def test_old_rows_without_document_fields_still_load() -> None:
    assert row().kinds_true == {} and row().expected_lane is None


def test_fairness_splits_payable_claims_by_member_tenure() -> None:
    from reimbursement_council.synthetic.metrics import fairness_metrics

    rows = [
        row(past_claims=0, lane="auto_reject"),
        row(past_claims=1, lane="auto_approve"),
        row(past_claims=5, lane="auto_approve"),
        row(past_claims=5, lane="human_review"),
        row(past_claims=9, lane="auto_reject", should_pay=False),
        row(past_claims=None),
    ]
    scores = fairness_metrics(rows, 3)
    assert scores["payable_new_members"] == 2 and scores["payable_tenured_members"] == 2
    assert scores["false_reject_rate_new"] == 0.5 and scores["false_reject_rate_tenured"] == 0.0
    assert scores["payable_recall_new"] == 0.5 and scores["payable_recall_tenured"] == 0.5


def test_with_a_simulated_fix_the_first_try_is_scored() -> None:
    from reimbursement_council.synthetic.metrics import heavy_damage_metrics

    fixed = row(damage="unreadable", first_lane="self_fix", lane="auto_approve", fix_tried=True,
                expected_lane="self_fix")  # fmt: skip
    assert heavy_damage_metrics([fixed], 100)["heavy_damage_self_fix_share"] == 1.0
    assert document_metrics([fixed])["expected_lane_match"] == 1.0
