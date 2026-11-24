"""Commands for real receipts: score the reader on SROIE (E1 and E11), and make claims with a
synthetic member and policy around real receipt photos (real end to end)."""

import argparse
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from reimbursement_council.adapters.ocr_engine import CachedOcrEngine, EasyOcrEngine
from reimbursement_council.adapters.readers import make_reader_for
from reimbursement_council.config.loader import load_settings
from reimbursement_council.core.extraction import extract_document
from reimbursement_council.core.models.claim import Document
from reimbursement_council.evaluation.sroie import compare_real, parse_sroie_key, summarize_real

logger = logging.getLogger(__name__)


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    read = commands.add_parser(
        "read-sroie", help="Score the reader on SROIE receipts (folder with img/ and key/)."
    )
    read.add_argument("folder", type=Path)
    read.add_argument("--reader", choices=["easyocr", "qr_only"], default=None)
    read.add_argument("--config-dir", type=Path, default=Path("config"))
    read.add_argument("--ocr-cache", type=Path, default=Path("data/cache/ocr"))
    read.add_argument("--results-name", default="accuracy.json")


def read_sroie(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    if args.reader:
        settings = settings.model_copy(
            update={"decision": settings.decision.model_copy(update={"reader": args.reader})}
        )
    images = sorted((args.folder / "img").glob("*.jpg"))
    if not images:
        raise ValueError(f"no receipts in {args.folder / 'img'}")
    pick = make_reader_for(settings, CachedOcrEngine(EasyOcrEngine(), args.ocr_cache))
    ratio = settings.documents.name_match_ratio
    rows = []
    started = time.time()
    for number, image in enumerate(images, start=1):
        key = json.loads((args.folder / "key" / f"{image.stem}.json").read_text(encoding="utf-8"))
        truth = parse_sroie_key(key)
        document = Document(
            document_id=image.stem,
            claim_id=image.stem,
            kind="receipt",
            file_path=str(image),
            image_hash=None,
            uploaded_at=datetime.now(UTC),
        )
        extraction = extract_document(image.stem, pick(document).read(document), settings)
        row = compare_real(truth, extraction, ratio)
        read = {
            name: (None if (f := extraction.best(name)) is None else f.value)
            for name in ("provider_name", "treatment_date", "total")
        }
        rows.append({"receipt": image.stem, **row, "truth": truth.model_dump(), "read": read})
        logger.info("receipt %d/%d %s: %s", number, len(images), image.stem, row)
    summary = summarize_real(rows)
    report = {
        "reader": settings.decision.reader,
        "seconds": round(time.time() - started, 1),
        "summary": summary,
        "rows": rows,
    }
    (args.folder / args.results_name).write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    lines = [f"receipts: {len(rows)}  reader: {settings.decision.reader}"]
    lines += [f"{name:<22} {value}" for name, value in summary.items() if name != "receipts"]
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


COMMANDS = {"read-sroie": read_sroie}
