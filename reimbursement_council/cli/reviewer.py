"""Commands for the AI case reviewer: run the golden check, show its health, and let a person
turn a benched reviewer back on (only after a passing check)."""

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from reimbursement_council.cli.data_dir import default_data_dir
from reimbursement_council.config.loader import load_settings
from reimbursement_council.pipeline.case_review import make_case_reviewer

logger = logging.getLogger(__name__)

EXIT_CHECK_FAILED = 1


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    for name, text in (
        ("check-reviewer", "Run the AI case reviewer on the golden set and record its health."),
        ("reviewer-enable", "Turn a benched AI case reviewer back on after a passing check."),
        ("reviewer-status", "Show whether the AI case reviewer is healthy or benched."),
    ):
        command = commands.add_parser(name, help=text)
        command.add_argument("--config-dir", type=Path, default=Path("config"))
        command.add_argument("--data-dir", type=Path, default=default_data_dir())


def check_reviewer(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    health, results = make_case_reviewer(settings, args.data_dir).run_check(datetime.now(UTC))
    lines = [
        f"{'pass' if r.passed else 'FAIL'}  {r.name:<36} expected {r.expected:<4} "
        f"{r.status}{f' ({r.problem})' if r.problem else ''} "
        f"score {'none' if r.score is None else f'{r.score:.2f}'}"
        for r in results
    ]
    lines.append(
        f"golden pass rate {health.golden_pass_rate or 0.0:.2f} "
        f"(limit {settings.decision.members.case_reviewer.golden_pass_rate:.2f}), "
        f"model {health.model}, prompt version {health.prompt_version}, state {health.status}"
    )
    if health.status == "benched":
        lines.append(f"benched: {health.bench_reason}")
        if health.last_check_passed:
            lines.append("the check passed: run reviewer-enable to turn it back on")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0 if health.last_check_passed else EXIT_CHECK_FAILED


def reviewer_enable(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    health = make_case_reviewer(settings, args.data_dir).enable()  # ValueError when not allowed
    sys.stdout.write(f"reviewer is {health.status} (model {health.model})\n")
    return 0


def reviewer_status(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    report = make_case_reviewer(settings, args.data_dir).health()
    sys.stdout.write(report.model_dump_json(indent=1) + "\n")
    return 0


COMMANDS = {
    "check-reviewer": check_reviewer,
    "reviewer-enable": reviewer_enable,
    "reviewer-status": reviewer_status,
}
