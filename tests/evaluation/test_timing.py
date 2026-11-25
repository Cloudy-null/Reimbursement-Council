import time
from datetime import UTC, datetime
from pathlib import Path

from reimbursement_council.core.models.claim import Document, ReaderOutput
from reimbursement_council.evaluation.timing import ReadClock, timing_metrics
from reimbursement_council.synthetic.metrics import RunRow


class SlowReader:
    def read(self, document: Document) -> ReaderOutput:
        time.sleep(0.02)
        return ReaderOutput(fields=[], line_items=[], qr_payloads=[])


def row(total: float | None, read: float | None) -> RunRow:
    return RunRow(
        name="c",
        lane="self_fix",
        outcome="queued",
        payout_calculated=None,
        p_good=0.5,
        combined_score=0.5,
        should_pay=True,
        correct_payout=0,
        defects=[],
        hard_rule_failed=False,
        damage="none",
        seconds_total=total,
        seconds_read=read,
    )


def test_read_clock_adds_up_read_time_and_resets(tmp_path: Path) -> None:
    clock = ReadClock(lambda document: SlowReader())
    document = Document(
        document_id="d1",
        claim_id="c1",
        kind="receipt",
        file_path=str(tmp_path / "x.png"),
        image_hash=None,
        uploaded_at=datetime(2026, 11, 25, tzinfo=UTC),
    )
    clock(document).read(document)
    clock(document).read(document)
    assert clock.seconds >= 0.04
    clock.reset()
    assert clock.seconds == 0.0


def test_timing_metrics_mean_median_max_and_stages() -> None:
    scores = timing_metrics([row(2.0, 1.5), row(4.0, 3.0), row(9.0, 8.0), row(None, None)])
    assert scores["timed_claims"] == 3
    assert scores["seconds_per_claim_mean"] == 5.0
    assert scores["seconds_per_claim_median"] == 4.0
    assert scores["seconds_per_claim_max"] == 9.0
    assert scores["seconds_read_mean"] == round(12.5 / 3, 3)
    assert scores["seconds_decide_mean"] == round(2.5 / 3, 3)


def test_no_timed_rows_gives_a_count_of_zero() -> None:
    assert timing_metrics([row(None, None)]) == {"timed_claims": 0}
