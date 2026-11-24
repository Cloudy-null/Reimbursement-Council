"""Commands for synthetic claim sets: make a set, run it through the pipeline and score it,
and fit the calibration on a run."""

import argparse
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import yaml

from reimbursement_council.adapters.document_drawing import draw_clinical_document
from reimbursement_council.adapters.files import load_claim_file, load_reference_file
from reimbursement_council.adapters.ocr_engine import CachedOcrEngine, EasyOcrEngine
from reimbursement_council.adapters.readers import make_reader_for
from reimbursement_council.adapters.receipt_drawing import DAMAGE_PRESETS, draw_receipt
from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.config.loader import load_settings
from reimbursement_council.config.models import Settings
from reimbursement_council.core.decision.calibration import fit_platt
from reimbursement_council.core.models.decision import Decision
from reimbursement_council.pipeline.process_claim import process_claim
from reimbursement_council.synthetic.claims import make_claim_set
from reimbursement_council.synthetic.document_metrics import MISMATCH_DEFECTS, document_metrics
from reimbursement_council.synthetic.metrics import RunRow, calibration_rows, metrics, paid_right

logger = logging.getLogger(__name__)


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    make = commands.add_parser("make-claims", help="Make a synthetic claim set with right answers.")
    make.add_argument("--count", type=int, default=100)
    make.add_argument("--seed", type=int, default=1)
    make.add_argument("--out", type=Path, required=True)
    make.add_argument("--config-dir", type=Path, default=Path("config"))

    run = commands.add_parser("run-set", help="Run a claim set through the pipeline and score it.")
    run.add_argument("folder", type=Path)
    run.add_argument("--reader", choices=["easyocr", "qr_only"], default=None)
    run.add_argument("--calibration", choices=["config", "on", "off"], default="config")
    run.add_argument("--cross-checks", choices=["config", "on", "off"], default="config")
    run.add_argument("--config-dir", type=Path, default=Path("config"))
    run.add_argument("--ocr-cache", type=Path, default=Path("data/cache/ocr"))
    run.add_argument("--results-name", default="results.json")
    run.add_argument(
        "--resume",
        action="store_true",
        help="Keep the results already stored for this run and only run the claims without one.",
    )

    fit = commands.add_parser("fit-calibration", help="Fit Platt calibration on a run-set result.")
    fit.add_argument("results", type=Path)
    fit.add_argument("--config-dir", type=Path, default=Path("config"))


SET_MANIFEST = "set.json"


def make_claims(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    if args.out.is_dir() and any(args.out.iterdir()):
        raise ValueError(
            f"{args.out} is not empty. Use a new folder, so two sets are never mixed in one."
        )
    claim_set = make_claim_set(args.seed, args.count, settings)
    args.out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "seed": args.seed,
        "count": len(claim_set.cases),
        "config_version": settings.config_version,
    }
    (args.out / SET_MANIFEST).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (args.out / "reference.json").write_text(
        claim_set.reference.model_dump_json(indent=1), encoding="utf-8"
    )
    for case in claim_set.cases:
        preset = DAMAGE_PRESETS[case.damage]
        index = int(case.name.rsplit("_", 1)[1])
        damage = None if preset is None else preset.model_copy(update={"seed": index})
        (args.out / f"{case.name}.png").write_bytes(draw_receipt(case.receipt, damage).png)
        for n, extra in enumerate(case.extra_documents, start=1):
            extra_preset = DAMAGE_PRESETS[extra.damage]
            extra_damage = (
                None
                if extra_preset is None
                else extra_preset.model_copy(update={"seed": index * 10 + n})
            )
            (args.out / extra.file_name).write_bytes(
                draw_clinical_document(extra.content, extra_damage).png
            )
        if case.fix is not None:  # the file the member sends when asked (self-fix)
            fixed = (
                draw_receipt(case.receipt).png
                if case.fix.clinical is None
                else draw_clinical_document(case.fix.clinical).png
            )
            (args.out / case.fix.file_name).write_bytes(fixed)
        (args.out / f"{case.name}.claim.json").write_text(
            case.claim.model_dump_json(indent=1), encoding="utf-8"
        )
        truth = case.truth.model_dump() | {
            "claim_id": case.claim.claim_id,
            "damage": case.damage,
            "duplicate_of": case.duplicate_of,
            "fix": None
            if case.fix is None
            else {
                "file": case.fix.file_name,
                "kind": case.fix.kind,
                "replace": case.fix.replace_document_id,
            },
        }
        (args.out / f"{case.name}.truth.json").write_text(
            json.dumps(truth, indent=1), encoding="utf-8"
        )
    logger.info("wrote %d claims to %s", len(claim_set.cases), args.out)
    return 0


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
    calibration and config. Otherwise it is started fresh.
    """
    stem = Path(args.results_name).stem
    db = args.folder / f"{stem}.sqlite"
    meta_path = args.folder / f"{stem}.run.json"
    meta = {
        "set_seed": manifest.get("seed"),
        "reader": settings.decision.reader,
        "calibration": settings.decision.calibration_enabled,
        "cross_checks": settings.decision.cross_checks_enabled,
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


def run_set(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    decision = settings.decision
    if args.reader:
        decision = decision.model_copy(update={"reader": args.reader})
    if args.calibration != "config":
        decision = decision.model_copy(update={"calibration_enabled": args.calibration == "on"})
    if args.cross_checks != "config":
        decision = decision.model_copy(update={"cross_checks_enabled": args.cross_checks == "on"})
    settings = settings.model_copy(update={"decision": decision})
    claim_paths = sorted(args.folder.glob("*.claim.json"))
    if not claim_paths:
        raise ValueError(f"no claims in {args.folder}: nothing to run")
    manifest = _read_manifest(args.folder, len(claim_paths))
    reference = load_reference_file(args.folder / "reference.json")
    store = _open_store(args, settings, manifest)
    pick = make_reader_for(settings, CachedOcrEngine(EasyOcrEngine(), args.ocr_cache))
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
        if result is None:
            logger.info("claim %d/%d %s: start", number, len(claim_paths), claim.claim_id)
            result = process_claim(
                claim, reference, settings, store, datetime.now(UTC), reader_for=pick
            )
        else:
            resumed += 1
        rows.append(
            RunRow(
                name=claim_path.name.replace(".claim.json", ""),
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
                kinds_read=dict(result.document_kinds),
                kinds_true=truth.get("document_kinds", {}),
                needs_flagged=[list(g) for g in result.needs_missing],
                needs_missing=truth.get("needs_missing", []),
                cross_check_failed=any(c.passed is False for c in result.cross_checks),
                cross_check_expected=bool(MISMATCH_DEFECTS & set(truth["defects"])),
                expected_lane=truth.get("expected_lane"),
            )
        )
    if resumed:
        logger.info("resumed: %d of %d claims came from the stored run", resumed, len(rows))
    scores = metrics(
        rows, decision.reviewer_time_value_halalas, decision.paid_right_tolerance_halalas
    ) | document_metrics(rows)
    lanes: dict[str, int] = {}
    for row in rows:
        lanes[row.lane] = lanes.get(row.lane, 0) + 1
    report = {
        "set": manifest,
        "reader": decision.reader,
        "calibration": decision.calibration_enabled,
        "cross_checks": decision.cross_checks_enabled,
        "config_version": settings.config_version,
        "seconds": round(time.time() - started, 1),
        "lanes": lanes,
        "metrics": scores,
        "rows": [row.model_dump() for row in rows],
    }
    (args.folder / args.results_name).write_text(json.dumps(report, indent=1), encoding="utf-8")
    calibrated = decision.calibration_enabled
    lines = [f"claims: {len(rows)}  reader: {decision.reader}  calibration: {calibrated}"]
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
