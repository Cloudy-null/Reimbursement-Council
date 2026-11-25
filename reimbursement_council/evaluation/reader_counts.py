"""Sums the local model reader's check counts over a set, for read-sroie and read-accuracy.

made_up_rate: values the model returned that are printed nowhere on the document (not in the
OCR text, not in the QR code), out of all values it returned. qr_mismatch_rate: total, date and
VAT number that differ from the QR code, out of those compared. Pure.
"""

from collections import Counter
from collections.abc import Iterable, Sequence
from statistics import median


def reader_summary(
    counts: Iterable[dict[str, int]], seconds: Sequence[float]
) -> dict[str, float | int]:
    total: Counter[str] = Counter()
    for one in counts:
        total.update(one)
    summary: dict[str, float | int] = {key: total[key] for key in sorted(total)}
    if total["returned"]:
        summary["made_up_rate"] = round(total["made_up"] / total["returned"], 4)
        summary["implausible_rate"] = round(total["implausible"] / total["returned"], 4)
    if total["qr_compared"]:
        summary["qr_mismatch_rate"] = round(total["qr_mismatch"] / total["qr_compared"], 4)
    if seconds:
        summary["seconds_per_document_mean"] = round(sum(seconds) / len(seconds), 3)
        summary["seconds_per_document_median"] = round(median(seconds), 3)
        summary["seconds_per_document_max"] = round(max(seconds), 3)
    return summary
