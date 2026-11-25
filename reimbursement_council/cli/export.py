"""Commands for the claim export (deliverable 2): write the JSON Schema, and run a whole claim
set through the pipeline and the export, checking every file against the schema."""

import argparse
import json
import logging
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from reimbursement_council.adapters.export_schema import SCHEMA_PATH, schema_errors, write_schema
from reimbursement_council.adapters.files import load_claim_file, load_reference_file
from reimbursement_council.adapters.ocr_engine import CachedOcrEngine, EasyOcrEngine
from reimbursement_council.adapters.readers import make_reader_for
from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.config.loader import load_settings
from reimbursement_council.pipeline.export_claim import export_claim
from reimbursement_council.pipeline.process_claim import process_claim

logger = logging.getLogger(__name__)

SUMMARY = "summary.json"


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    schema = commands.add_parser("write-schema", help="Write the claim export JSON Schema.")
    schema.add_argument("--out", type=Path, default=SCHEMA_PATH)

    export = commands.add_parser(
        "export-set", help="Decide every claim in a set, export it and check it against the schema."
    )
    export.add_argument("folder", type=Path)
    export.add_argument("--out", type=Path, default=Path("outputs/export"))
    export.add_argument("--reader", choices=["easyocr", "qr_only"], default=None)
    export.add_argument("--config-dir", type=Path, default=Path("config"))
    export.add_argument("--ocr-cache", type=Path, default=Path("data/cache/ocr"))


def write_schema_command(args: argparse.Namespace) -> int:
    write_schema(args.out)
    logger.info("wrote the claim export schema to %s", args.out)
    return 0


def export_set(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    if args.reader:
        settings = settings.model_copy(
            update={"decision": settings.decision.model_copy(update={"reader": args.reader})}
        )
    claim_paths = sorted(args.folder.glob("*.claim.json"))
    if not claim_paths:
        raise ValueError(f"no claims in {args.folder}: nothing to export")
    reference = load_reference_file(args.folder / "reference.json")
    args.out.mkdir(parents=True, exist_ok=True)
    database = args.out / "export.sqlite"
    database.unlink(missing_ok=True)  # every export-set run starts fresh
    store = ClaimStore(database)
    pick = make_reader_for(settings, CachedOcrEngine(EasyOcrEngine(), args.ocr_cache))
    lanes: Counter[str] = Counter()
    invalid: dict[str, list[str]] = {}
    ready = 0
    for number, path in enumerate(claim_paths, start=1):
        claim = load_claim_file(path)
        now = datetime.now(UTC)
        process_claim(claim, reference, settings, store, now, reader_for=pick)
        export = export_claim(claim, store, reference, settings, now)
        if export is None:
            raise ValueError(f"{claim.claim_id}: decided but no export was made")
        data = json.loads(export.model_dump_json())
        errors = schema_errors(data)
        if errors:
            invalid[claim.claim_id] = errors[:5]
        lanes[export.decision.lane] += 1
        ready += export.ready_for_processing
        (args.out / f"{claim.claim_id}.json").write_text(
            json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        logger.info(
            "export %d/%d %s: %s", number, len(claim_paths), claim.claim_id, export.decision.lane
        )
    summary = {
        "set": str(args.folder),
        "claims": len(claim_paths),
        "valid": len(claim_paths) - len(invalid),
        "invalid": len(invalid),
        "ready_for_processing": ready,
        "lanes": dict(lanes),
        "reader": settings.decision.reader,
        "config_version": settings.config_version,
        "schema": str(SCHEMA_PATH.name),
        "errors": invalid,
    }
    (args.out / SUMMARY).write_text(json.dumps(summary, indent=1), encoding="utf-8")
    sys.stdout.write(
        f"claims: {summary['claims']}  valid: {summary['valid']}  invalid: {summary['invalid']}  "
        f"ready: {ready}\nlanes: {dict(lanes)}\n"
    )
    return 0 if not invalid else 2


COMMANDS = {"write-schema": write_schema_command, "export-set": export_set}
