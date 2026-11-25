"""Turns one live claim's export and timings into a short record, and many into a summary.

Pure: works on the export JSON (dict) the website gave back. The live test has no right
answers, so this records what happened (lane, what the member was asked, what was read, how
long it took); a person judges by eye whether it was right.
"""

from collections import Counter
from collections.abc import Sequence
from statistics import median
from typing import Any


def claim_record(
    name: str,
    files: list[str],
    export: dict[str, Any],
    seconds: dict[str, float],
    schema_errors: list[str],
) -> dict[str, Any]:
    decision = export.get("decision") or {}
    documents = export.get("documents") or []
    request = decision.get("self_fix_request") or {}
    message = decision.get("member_message") or {}
    return {
        "name": name,
        "files": files,
        "seconds": {k: round(v, 3) for k, v in seconds.items()},
        "lane": decision.get("lane"),
        "reason": decision.get("reason"),
        "asked_member": request.get("message_en") or message.get("en"),
        "missing_documents": export.get("missing_documents") or [],
        "cross_checks_failed": [
            c.get("name") for c in export.get("cross_checks") or [] if c.get("passed") is False
        ],
        "kinds": [d.get("kind") for d in documents],
        "fields": {
            d.get("document_id", "?"): [
                {
                    "name": f.get("name"),
                    "value": f.get("value"),
                    "source": f.get("source"),
                    "confidence": f.get("confidence"),
                }
                for f in d.get("fields") or []
            ]
            for d in documents
        },
        "ready_for_processing": export.get("ready_for_processing"),
        "schema_valid": not schema_errors,
        "error": None,
    }


def failed_record(
    name: str, files: list[str], seconds: dict[str, float], error: str
) -> dict[str, Any]:
    return {
        "name": name,
        "files": files,
        "seconds": {k: round(v, 3) for k, v in seconds.items()},
        "lane": None,
        "error": error,
    }


def live_summary(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    done = [r for r in records if r.get("error") is None]
    totals = [r["seconds"]["total"] for r in done if "total" in r["seconds"]]
    summary: dict[str, Any] = {
        "claims": len(records),
        "finished": len(done),
        "errors": len(records) - len(done),
        "lanes": dict(Counter(str(r["lane"]) for r in done)),
        "schema_valid": sum(bool(r.get("schema_valid")) for r in done),
    }
    if totals:
        summary |= {
            "seconds_per_claim_mean": round(sum(totals) / len(totals), 3),
            "seconds_per_claim_median": round(median(totals), 3),
            "seconds_per_claim_max": round(max(totals), 3),
        }
    for stage in ("upload_and_read", "send_and_decide"):
        values = [r["seconds"][stage] for r in done if stage in r["seconds"]]
        if values:
            summary[f"seconds_{stage}_mean"] = round(sum(values) / len(values), 3)
    return summary
