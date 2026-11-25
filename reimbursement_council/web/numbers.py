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


HEADLINE = Path(__file__).with_name("headline.json")
# Switch names in plain words, for the ablation table on the numbers page.
PLAIN = {
    "arithmetic_checks_enabled=false": "Arithmetic checks off",
    "two_readers_enabled=false": "Second reader (OCR check) off",
    "self_fix_enabled=false": "Asking the member off",
    "members.case_reviewer.enabled=false": "AI reviewer off",
    "members.case_reviewer.enabled=true": "AI reviewer on",
    "disagreement_routing_enabled=false": "Disagreement routing off",
    "cost_lanes_enabled=false": "Cost-based lanes off",
    "members.history_member.enabled=false": "Member history off",
}
ABLATION_FOLDER = "check_v2"
DEFAULT_RUN = "Everything on (the default)"


def load_headline(path: Path = HEADLINE) -> dict[str, Any]:
    return _load(path) or {}


def plain_change(report: dict[str, Any]) -> str:
    """What a run changed, in plain words (the ablation table)."""
    parts = [PLAIN.get(o, o) for o in report.get("overrides", [])]
    if report.get("simulate_fix"):
        parts.append("member fixes simulated")
    if report.get("reader") == "easyocr":
        parts.append("OCR only (no AI reader)")
    if report.get("calibration") is False:
        parts.append("calibration off")
    if report.get("cross_checks") is False:
        parts.append("document cross checks off")
    return ", ".join(parts) or DEFAULT_RUN


def ablation_runs(root: Path) -> list[dict[str, Any]]:
    """The runs on the current synthetic check set, one row per change, plain names."""
    rows: dict[str, dict[str, Any]] = {}
    for run in find_runs(root):
        if not run["name"].startswith(ABLATION_FOLDER + " /"):
            continue
        name = plain_change(run["report"])
        rows[name] = {"name": name, "report": run["report"]}
    return sorted(rows.values(), key=lambda r: (r["name"] != DEFAULT_RUN, r["name"]))
