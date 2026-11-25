"""fit-calibration: fit Platt calibration on a run-set result and write config/calibration.yaml."""

import argparse
import json
import sys

import yaml

from reimbursement_council.config.loader import load_settings
from reimbursement_council.core.decision.calibration import fit_platt
from reimbursement_council.synthetic.metrics import RunRow, calibration_rows, paid_right


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
