"""make-claims: a synthetic claim set with right answers, one image per document and the
fixed files for self-fix. run-set and fit-calibration are in run_set.py."""

import argparse
import json
import logging
from pathlib import Path

from reimbursement_council.adapters.document_drawing import draw_clinical_document
from reimbursement_council.adapters.receipt_drawing import DAMAGE_PRESETS, draw_receipt
from reimbursement_council.config.loader import load_settings
from reimbursement_council.synthetic.claims import make_claim_set

logger = logging.getLogger(__name__)


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    make = commands.add_parser("make-claims", help="Make a synthetic claim set with right answers.")
    make.add_argument("--count", type=int, default=100)
    make.add_argument("--seed", type=int, default=1)
    make.add_argument("--out", type=Path, required=True)
    make.add_argument("--config-dir", type=Path, default=Path("config"))


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
