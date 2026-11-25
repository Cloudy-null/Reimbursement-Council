"""Find the measured runs for the numbers page: every run-set result and every reader score
under the data folder, found by what the file holds, not by its name."""

import json
from pathlib import Path
from typing import Any

SKIP_SUFFIXES = (".claim.json", ".truth.json", ".run.json")


def _load(path: Path) -> dict[str, Any] | None:
    if path.name.endswith(SKIP_SUFFIXES) or path.name in ("set.json", "reference.json"):
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def changed(report: dict[str, Any]) -> str:
    """What this run changed from the config, in a few words."""
    parts = list(report.get("overrides", []))
    if report.get("simulate_fix"):
        parts.append("member fix simulated")
    if report.get("calibration"):
        parts.append("calibration on")
    if report.get("cross_checks") is False:
        parts.append("cross checks off")
    return ", ".join(parts) or "config as is"


def find_runs(root: Path) -> list[dict[str, Any]]:
    runs = []
    for path in sorted(root.glob("sets/**/*.json")):
        report = _load(path)
        if report and {"metrics", "lanes", "rows"} <= set(report):
            name = f"{path.parent.name} / {path.stem}"
            runs.append({"name": name, "report": report, "changed": changed(report)})
    return runs


def find_reader_scores(root: Path) -> list[dict[str, Any]]:
    scores = []
    for path in sorted(root.glob("**/accuracy*.json")):
        report = _load(path)
        if report and "summary" in report:
            scores.append(
                {
                    "name": f"{path.parent.name} / {path.stem}",
                    "summary": report["summary"],
                    "reader": report.get("reader", ""),
                }  # fmt: skip
            )
    return scores
