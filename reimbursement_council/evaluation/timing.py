"""Seconds per claim and per stage, for the harness and the value slide.

ReadClock wraps any reader picker and adds up the time spent reading documents. The rest of a
claim's time (checks, rules, council, lanes, saving) is "decide". With the OCR cache on, reading
is mostly a file load, so honest live timings need a run without the cache.
"""

import time
from collections.abc import Callable, Sequence
from statistics import median

from reimbursement_council.adapters.readers import DocumentReader
from reimbursement_council.core.models.claim import Document, ReaderOutput
from reimbursement_council.synthetic.metrics import RunRow

Picker = Callable[[Document], DocumentReader]


class ReadClock:
    """Picks readers through `pick` and adds up how long their reads take."""

    def __init__(self, pick: Picker) -> None:
        self._pick = pick
        self.seconds = 0.0

    def reset(self) -> None:
        self.seconds = 0.0

    def __call__(self, document: Document) -> DocumentReader:
        return _TimedReader(self._pick(document), self)


class _TimedReader:
    def __init__(self, reader: DocumentReader, clock: ReadClock) -> None:
        self._reader = reader
        self._clock = clock

    def read(self, document: Document) -> ReaderOutput:
        started = time.perf_counter()
        try:
            return self._reader.read(document)
        finally:
            self._clock.seconds += time.perf_counter() - started


def timing_metrics(rows: Sequence[RunRow]) -> dict[str, float | int]:
    """Mean, median and slowest seconds per claim, and the mean read and decide seconds.

    Only rows that carry a timing count (a resumed row has none)."""
    timed = [r for r in rows if r.seconds_total is not None and r.seconds_read is not None]
    if not timed:
        return {"timed_claims": 0}
    totals = [r.seconds_total for r in timed if r.seconds_total is not None]
    reads = [r.seconds_read for r in timed if r.seconds_read is not None]
    return {
        "timed_claims": len(timed),
        "seconds_per_claim_mean": round(sum(totals) / len(totals), 3),
        "seconds_per_claim_median": round(median(totals), 3),
        "seconds_per_claim_max": round(max(totals), 3),
        "seconds_read_mean": round(sum(reads) / len(reads), 3),
        "seconds_decide_mean": round(
            sum(t - r for t, r in zip(totals, reads, strict=True)) / len(totals), 3
        ),
    }
