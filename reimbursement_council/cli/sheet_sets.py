"""make-optical-claims and make-dental-claims: claim sets whose documents are printed sheets,
written in the make-claims file format (N.claim.json, N.truth.json, N.png, N-k.png extra
documents, N-fix.png, reference.json, set.json), so run-set can score them."""

import argparse
import json
import logging
from pathlib import Path

from reimbursement_council.adapters.sheet_drawing import draw_sheet
from reimbursement_council.config.loader import load_settings
from reimbursement_council.config.models import Settings
from reimbursement_council.synthetic.optical_claims import make_optical_set
from reimbursement_council.synthetic.sheet_cases import SheetSet

logger = logging.getLogger(__name__)

SET_MANIFEST = "set.json"


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    for name, what in (
        ("make-optical-claims", "an optical claim set (glasses) with right answers"),
    ):
        command = commands.add_parser(name, help=f"Make {what}.")
        command.add_argument("out", type=Path, help="A new, empty folder.")
        command.add_argument("--seed", type=int, default=1)
        command.add_argument("--config-dir", type=Path, default=Path("config"))


def ensure_empty(folder: Path) -> None:
    if folder.is_dir() and any(folder.iterdir()):
        raise ValueError(f"{folder} is not empty. Use a new folder, so two sets are never mixed.")


def write_sheet_set(sheet_set: SheetSet, out: Path, settings: Settings) -> None:
    ensure_empty(out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "seed": sheet_set.seed,
        "count": len(sheet_set.cases),
        "config_version": settings.config_version,
        "label": sheet_set.label,
        "kind": sheet_set.kind,
    }
    (out / SET_MANIFEST).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    (out / "reference.json").write_text(
        sheet_set.reference.model_dump_json(indent=1), encoding="utf-8"
    )
    for case in sheet_set.cases:
        for document in case.documents:
            (out / document.file_name).write_bytes(draw_sheet(document.sheet).png)
        if case.fix is not None:
            (out / case.fix.file_name).write_bytes(draw_sheet(case.fix.sheet).png)
        (out / f"{case.name}.claim.json").write_text(
            case.claim.model_dump_json(indent=1), encoding="utf-8"
        )
        truth = case.truth.model_dump() | {
            "claim_id": case.claim.claim_id,
            "damage": "none",
            "duplicate_of": None,
            "fix": None
            if case.fix is None
            else {
                "file": case.fix.file_name,
                "kind": case.fix.kind,
                "replace": case.fix.replace_document_id,
            },
            "scenario": case.scenario,
            "fields": case.fields,
        }
        (out / f"{case.name}.truth.json").write_text(
            json.dumps(truth, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    logger.info("wrote %d %s claims to %s", len(sheet_set.cases), sheet_set.kind, out)


def make_optical_claims(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    write_sheet_set(make_optical_set(args.seed, settings), args.out, settings)
    return 0


COMMANDS = {
    "make-optical-claims": make_optical_claims,
}
