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

from reimbursement_council.adapters.files import load_claim_file, load_reference_file
from reimbursement_council.adapters.ocr_engine import CachedOcrEngine, EasyOcrEngine
from reimbursement_council.adapters.readers import make_reader_for
from reimbursement_council.adapters.receipt_drawing import DAMAGE_PRESETS, draw_receipt
from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.config.loader import load_settings
from reimbursement_council.core.decision.calibration import fit_platt
from reimbursement_council.pipeline.process_claim import process_claim
from reimbursement_council.synthetic.claims import make_claim_set
from reimbursement_council.synthetic.metrics import RunRow, metrics, paid_right

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
    run.add_argument("--config-dir", type=Path, default=Path("config"))
    run.add_argument("--ocr-cache", type=Path, default=Path("data/cache/ocr"))
    run.add_argument("--results-name", default="results.json")

    fit = commands.add_parser("fit-calibration", help="Fit Platt calibration on a run-set result.")
    fit.add_argument("results", type=Path)
    fit.add_argument("--config-dir", type=Path, default=Path("config"))


def make_claims(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    claim_set = make_claim_set(args.seed, args.count, settings)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "reference.json").write_text(
        claim_set.reference.model_dump_json(indent=1), encoding="utf-8"
    )
    for case in claim_set.cases:
        preset = DAMAGE_PRESETS[case.damage]
        index = int(case.name.rsplit("_", 1)[1])
        damage = None if preset is None else preset.model_copy(update={"seed": index})
        (args.out / f"{case.name}.png").write_bytes(draw_receipt(case.receipt, damage).png)
        (args.out / f"{case.name}.claim.json").write_text(
            case.claim.model_dump_json(indent=1), encoding="utf-8"
        )
        truth = case.truth.model_dump() | {"damage": case.damage, "duplicate_of": case.duplicate_of}
        (args.out / f"{case.name}.truth.json").write_text(
            json.dumps(truth, indent=1), encoding="utf-8"
        )
    logger.info("wrote %d claims to %s", len(claim_set.cases), args.out)
    return 0


def run_set(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    decision = settings.decision
    if args.reader:
        decision = decision.model_copy(update={"reader": args.reader})
    if args.calibration != "config":
        decision = decision.model_copy(update={"calibration_enabled": args.calibration == "on"})
    settings = settings.model_copy(update={"decision": decision})
    reference = load_reference_file(args.folder / "reference.json")
    db = args.folder / "run.sqlite"
    db.unlink(missing_ok=True)
    store = ClaimStore(db)
    pick = make_reader_for(settings, CachedOcrEngine(EasyOcrEngine(), args.ocr_cache))
    rows: list[RunRow] = []
    started = time.time()
    for claim_path in sorted(args.folder.glob("*.claim.json")):
        truth = json.loads(
            claim_path.with_name(claim_path.name.replace(".claim.json", ".truth.json")).read_text(
                encoding="utf-8"
            )
        )
        claim = load_claim_file(claim_path)
        result = process_claim(
            claim, reference, settings, store, datetime.now(UTC), reader_for=pick
        )
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
            )
        )
    scores = metrics(
        rows, decision.reviewer_time_value_halalas, decision.paid_right_tolerance_halalas
    )
    lanes: dict[str, int] = {}
    for row in rows:
        lanes[row.lane] = lanes.get(row.lane, 0) + 1
    report = {
        "reader": decision.reader,
        "calibration": decision.calibration_enabled,
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
    lines += [f"{name:<24} {value}" for name, value in scores.items()]
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


def fit_calibration(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    report = json.loads(args.results.read_text(encoding="utf-8"))
    rows = [RunRow.model_validate(row) for row in report["rows"]]
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
                "fitted_on": f"{args.results} ({len(rows)} claims)",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    sys.stdout.write(f"a={params.a:.4f} b={params.b:.4f} written to {target}\n")
    return 0
