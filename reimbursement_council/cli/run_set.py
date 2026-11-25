"""run-set: run a claim set through the pipeline and score it. fit-calibration: fit Platt on a
run. One switch at a time can be changed with --set for ablations (run-ablation skill)."""

import argparse
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from reimbursement_council.adapters.files import load_claim_file, load_reference_file
from reimbursement_council.adapters.ocr_engine import CachedOcrEngine, EasyOcrEngine, OcrEngine
from reimbursement_council.adapters.readers import make_reader_for
from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.config.loader import load_settings
from reimbursement_council.config.models import DecisionConfig, Settings
from reimbursement_council.core.decision.calibration import fit_platt
from reimbursement_council.core.models.claim import Claim
from reimbursement_council.core.models.decision import Decision
from reimbursement_council.core.models.reference import ReferenceData
from reimbursement_council.evaluation.timing import ReadClock, timing_metrics
from reimbursement_council.pipeline.process_claim import process_claim
from reimbursement_council.synthetic.apply_fix import claim_after_fix
from reimbursement_council.synthetic.document_metrics import MISMATCH_DEFECTS, document_metrics
from reimbursement_council.synthetic.metrics import (
    RunRow,
    calibration_rows,
    fairness_metrics,
    metrics,
    paid_right,
    self_fix_metrics,
)

logger = logging.getLogger(__name__)

SET_MANIFEST = "set.json"


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    run = commands.add_parser("run-set", help="Run a claim set through the pipeline and score it.")
    run.add_argument("folder", type=Path)
    run.add_argument("--reader", choices=["easyocr", "qr_only", "ollama"], default=None)
    run.add_argument("--calibration", choices=["config", "on", "off"], default="config")
    run.add_argument("--cross-checks", choices=["config", "on", "off"], default="config")
    run.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Change one decision.yaml setting for this run, for example "
        "arithmetic_checks_enabled=false or members.history_member.enabled=false.",
    )
    run.add_argument(
        "--simulate-fix",
        action="store_true",
        help="When a claim goes to self_fix and the set has its fixed file, send it and decide "
        "again, as the member would (E8).",
    )
    run.add_argument("--config-dir", type=Path, default=Path("config"))
    run.add_argument("--ocr-cache", type=Path, default=Path("data/cache/ocr"))
    run.add_argument(
        "--no-ocr-cache",
        action="store_true",
        help="Read every image again, for honest seconds per claim.",
    )
    run.add_argument("--results-name", default="results.json")
    run.add_argument(
        "--resume",
        action="store_true",
        help="Keep the results already stored for this run and only run the claims without one.",
    )

    fit = commands.add_parser("fit-calibration", help="Fit Platt calibration on a run-set result.")
    fit.add_argument("results", type=Path)
    fit.add_argument("--config-dir", type=Path, default=Path("config"))


def with_overrides(decision: DecisionConfig, overrides: list[str]) -> DecisionConfig:
    """decision.yaml with KEY=VALUE changes (dotted keys reach inside members and ocr). The
    result is validated again, so a typo or a bad value stops the run."""
    data: dict[str, Any] = decision.model_dump()
    for item in overrides:
        key, sep, raw = item.partition("=")
        if not sep:
            raise ValueError(f"--set needs KEY=VALUE, got {item!r}")
        parts = key.strip().split(".")
        target = data
        for part in parts[:-1]:
            if part not in target or not isinstance(target[part], dict):
                raise ValueError(f"--set: unknown setting {key!r}")
            target = target[part]
        if parts[-1] not in target:
            raise ValueError(f"--set: unknown setting {key!r}")
        target[parts[-1]] = yaml.safe_load(raw)
    return DecisionConfig.model_validate(data)


def _settings_for(args: argparse.Namespace) -> Settings:
    settings = load_settings(args.config_dir)
    decision = settings.decision
    if args.reader:
        decision = decision.model_copy(update={"reader": args.reader})
    if args.calibration != "config":
        decision = decision.model_copy(update={"calibration_enabled": args.calibration == "on"})
    if args.cross_checks != "config":
        decision = decision.model_copy(update={"cross_checks_enabled": args.cross_checks == "on"})
    decision = with_overrides(decision, args.set)
    return settings.model_copy(update={"decision": decision})


def _read_manifest(folder: Path, claim_count: int) -> dict[str, object]:
    """The set's seed and size, checked against the claim files that are really there."""
    path = folder / SET_MANIFEST
    if not path.is_file():
        raise ValueError(f"{folder} has no {SET_MANIFEST}. Make the set with make-claims.")
    manifest: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("count") != claim_count:
        raise ValueError(
            f"{folder} has {claim_count} claim files, "
            f"but {SET_MANIFEST} says {manifest.get('count')}"
        )
    return manifest


def _open_store(
    args: argparse.Namespace, settings: Settings, manifest: dict[str, object]
) -> ClaimStore:
    """The run's own database, named after the results file so two runs in one folder (for
    example calibration off and on) never share stored decisions.

    With --resume the database is kept, but only if it was made with the same reader,
    switches and config. Otherwise it is started fresh.
    """
    stem = Path(args.results_name).stem
    db = args.folder / f"{stem}.sqlite"
    meta_path = args.folder / f"{stem}.run.json"
    meta = {
        "set_seed": manifest.get("seed"),
        "reader": settings.decision.reader,
        "calibration": settings.decision.calibration_enabled,
        "cross_checks": settings.decision.cross_checks_enabled,
        "overrides": list(args.set),
        "simulate_fix": args.simulate_fix,
        "config_version": settings.config_version,
    }
    if args.resume and db.is_file():
        stored = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else None
        if stored != meta:
            raise ValueError(
                f"cannot resume {db}: it was made with {stored}, this run is {meta}. "
                "Run again without --resume to start fresh."
            )
    else:
        db.unlink(missing_ok=True)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    return ClaimStore(db)


def _stored_result(store: ClaimStore, claim_id: str) -> Decision | None:
    """A claim is done only when both its decision and its receipt are stored (they are saved
    in two steps, so a run killed between them must run that claim again)."""
    decision = store.load_decision(claim_id)
    return decision if decision is not None and store.has_receipt(claim_id) else None


def _row(
    name: str,
    result: Decision,
    truth: dict[str, Any],
    first: Decision | None,
    past_claims: int | None,
) -> RunRow:
    # The truth's documents are those of the first try, so they are scored on it.
    read = first or result
    return RunRow(
        name=name,
        lane=result.lane,
        outcome=result.outcome,
        payout_calculated=result.payout_calculated,
        p_good=result.p_good,
        combined_score=result.combined_score,
        should_pay=truth["should_pay"],
        correct_payout=truth["correct_payout"],
        defects=truth["defects"],
        damage=truth["damage"],
        hard_rule_failed=any(r.outcome == "fail" for r in result.rule_results),
        kinds_read=dict(read.document_kinds),
        kinds_true=truth.get("document_kinds", {}),
        needs_flagged=[list(g) for g in read.needs_missing],
        needs_missing=truth.get("needs_missing", []),
        cross_check_failed=any(c.passed is False for c in read.cross_checks),
        cross_check_expected=bool(MISMATCH_DEFECTS & set(truth["defects"])),
        expected_lane=truth.get("expected_lane"),
        first_lane=None if first is None else first.lane,
        fix_tried=first is not None,
        past_claims=past_claims,
    )


def _past_claims(reference: ReferenceData, claim: Claim) -> int | None:
    try:
        return reference.history(claim.patient_member_id).past_claims
    except LookupError:
        return None


def run_set(args: argparse.Namespace) -> int:
    settings = _settings_for(args)
    decision = settings.decision
    claim_paths = sorted(args.folder.glob("*.claim.json"))
    if not claim_paths:
        raise ValueError(f"no claims in {args.folder}: nothing to run")
    manifest = _read_manifest(args.folder, len(claim_paths))
    reference = load_reference_file(args.folder / "reference.json")
    store = _open_store(args, settings, manifest)
    engine: OcrEngine = EasyOcrEngine()
    if not args.no_ocr_cache:
        engine = CachedOcrEngine(engine, args.ocr_cache)
    pick = ReadClock(make_reader_for(settings, engine))
    rows: list[RunRow] = []
    started = time.time()
    resumed = 0
    for number, claim_path in enumerate(claim_paths, start=1):
        truth = json.loads(
            claim_path.with_name(claim_path.name.replace(".claim.json", ".truth.json")).read_text(
                encoding="utf-8"
            )
        )
        claim = load_claim_file(claim_path)
        if truth.get("claim_id") != claim.claim_id:
            raise ValueError(
                f"{claim_path.name}: truth is for {truth.get('claim_id')}, "
                f"claim is {claim.claim_id}"
            )
        result = _stored_result(store, claim.claim_id) if args.resume else None
        first: Decision | None = None
        if result is None:
            logger.info("claim %d/%d %s: start", number, len(claim_paths), claim.claim_id)
            now = datetime.now(UTC)
            pick.reset()
            claim_started = time.perf_counter()
            result = process_claim(claim, reference, settings, store, now, reader_for=pick)
            seconds = (time.perf_counter() - claim_started, pick.seconds)
            fix = truth.get("fix")
            if args.simulate_fix and result.lane == "self_fix" and fix:
                first = result
                fixed = claim_after_fix(claim, fix, args.folder, result.self_fix_request, now)
                result = process_claim(fixed, reference, settings, store, now, reader_for=pick)
                logger.info("claim %s: after the fix, lane %s", claim.claim_id, result.lane)
        else:
            resumed += 1
            seconds = None
        name = claim_path.name.replace(".claim.json", "")
        row = _row(name, result, truth, first, _past_claims(reference, claim))
        if seconds is not None:
            row = row.model_copy(update={"seconds_total": seconds[0], "seconds_read": seconds[1]})
        rows.append(row)
    if resumed:
        logger.info("resumed: %d of %d claims came from the stored run", resumed, len(rows))
    tolerance = decision.paid_right_tolerance_halalas
    scores = (
        metrics(rows, decision.reviewer_time_value_halalas, tolerance)
        | document_metrics(rows)
        | self_fix_metrics(rows, tolerance)
        | fairness_metrics(rows, decision.members.history_member.min_past_claims)
        | timing_metrics(rows)
    )
    lanes: dict[str, int] = {}
    for row in rows:
        lanes[row.lane] = lanes.get(row.lane, 0) + 1
    report = {
        "set": manifest,
        "reader": decision.reader,
        "calibration": decision.calibration_enabled,
        "cross_checks": decision.cross_checks_enabled,
        "overrides": list(args.set),
        "simulate_fix": args.simulate_fix,
        "ocr_cache": not args.no_ocr_cache,
        "config_version": settings.config_version,
        "seconds": round(time.time() - started, 1),
        "lanes": lanes,
        "metrics": scores,
        "rows": [row.model_dump() for row in rows],
    }
    (args.folder / args.results_name).write_text(json.dumps(report, indent=1), encoding="utf-8")
    calibrated = decision.calibration_enabled
    lines = [f"claims: {len(rows)}  reader: {decision.reader}  calibration: {calibrated}"]
    lines += [f"overrides: {list(args.set)}  simulate_fix: {args.simulate_fix}"]
    lines += [f"lanes: {lanes}"]
    lines += [f"{name:<36} {value}" for name, value in scores.items()]
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


def fit_calibration(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    report = json.loads(args.results.read_text(encoding="utf-8"))
    all_rows = [RunRow.model_validate(row) for row in report["rows"]]
    rows = calibration_rows(all_rows)
    tolerance = settings.decision.paid_right_tolerance_halalas
    params = fit_platt(
        [r.combined_score for r in rows], [1 if paid_right(r, tolerance) else 0 for r in rows]
    )
    target = args.config_dir / "calibration.yaml"
    target.write_text(
        "# Platt calibration, fitted by: reimbursement-council fit-calibration\n"
        + yaml.safe_dump(
            {
                "method": "platt",
                "a": round(params.a, 6),
                "b": round(params.b, 6),
                "fitted_on": (
                    f"{args.results} ({len(rows)} claims; "
                    f"{len(all_rows) - len(rows)} rejected by a hard rule left out)"
                ),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    sys.stdout.write(f"a={params.a:.4f} b={params.b:.4f} written to {target}\n")
    return 0


COMMANDS = {"run-set": run_set, "fit-calibration": fit_calibration}
