"""Commands for real receipts: score the reader on SROIE (E1 and E11), and make claims with a
synthetic member and policy around real receipt photos (real end to end)."""

import argparse
import json
import logging
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from reimbursement_council.adapters.ocr_engine import CachedOcrEngine, EasyOcrEngine
from reimbursement_council.adapters.readers import make_reader_for
from reimbursement_council.config.loader import load_settings
from reimbursement_council.core.extraction import extract_document
from reimbursement_council.core.models.claim import Document
from reimbursement_council.evaluation.reader_counts import reader_summary
from reimbursement_council.evaluation.real_claims import real_claim, real_reference
from reimbursement_council.evaluation.sroie import compare_real, parse_sroie_key, summarize_real

logger = logging.getLogger(__name__)


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    read = commands.add_parser(
        "read-sroie", help="Score the reader on SROIE receipts (folder with img/ and key/)."
    )
    read.add_argument("folder", type=Path)
    read.add_argument("--reader", choices=["easyocr", "qr_only", "ollama"], default=None)
    read.add_argument("--config-dir", type=Path, default=Path("config"))
    read.add_argument("--ocr-cache", type=Path, default=Path("data/cache/ocr"))
    read.add_argument("--results-name", default="accuracy.json")
    read.add_argument(
        "--two-readers",
        choices=["config", "on", "off"],
        default="config",
        help="With --reader ollama: let EasyOCR check the model field by field.",
    )

    make = commands.add_parser(
        "make-real-claims",
        help="Wrap real SROIE receipts in synthetic claims (member, policy, dates) for run-set.",
    )
    make.add_argument("folder", type=Path)
    make.add_argument("--out", type=Path, required=True)
    make.add_argument("--seed", type=int, default=1)
    make.add_argument("--count", type=int, default=50)
    make.add_argument("--config-dir", type=Path, default=Path("config"))


def read_sroie(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    changes: dict[str, object] = {}
    if args.reader:
        changes["reader"] = args.reader
    if args.two_readers != "config":
        changes["two_readers_enabled"] = args.two_readers == "on"
    settings = settings.model_copy(
        update={"decision": settings.decision.model_copy(update=changes)}
    )
    images = sorted((args.folder / "img").glob("*.jpg"))
    if not images:
        raise ValueError(f"no receipts in {args.folder / 'img'}")
    pick = make_reader_for(settings, CachedOcrEngine(EasyOcrEngine(), args.ocr_cache))
    ratio = settings.documents.name_match_ratio
    rows = []
    counts: list[dict[str, int]] = []
    seconds: list[float] = []
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
        read_started = time.perf_counter()
        output = pick(document).read(document)
        seconds.append(time.perf_counter() - read_started)
        counts.append(output.reader_counts)
        extraction = extract_document(image.stem, output, settings)
        row = compare_real(truth, extraction, ratio)
        read = {
            name: (None if (f := extraction.best(name)) is None else f.value)
            for name in ("provider_name", "treatment_date", "total")
        }
        rows.append({"receipt": image.stem, **row, "truth": truth.model_dump(), "read": read})
        logger.info("receipt %d/%d %s: %s", number, len(images), image.stem, row)
    summary = summarize_real(rows) | reader_summary(counts, seconds)
    report = {
        "reader": settings.decision.reader,
        "two_readers": settings.decision.two_readers_enabled,
        "model": settings.local_model.model if settings.decision.reader == "ollama" else None,
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


def make_real_claims(args: argparse.Namespace) -> int:
    """One claim per receipt. The truth says the claim should be paid: the policy is active, it
    is sent on time, and nothing is wrong except what the reader gets wrong. The right payout is
    not known (the services are not on our price list), so it is 0 and not scored."""
    settings = load_settings(args.config_dir)
    if args.out.is_dir() and any(args.out.iterdir()):
        raise ValueError(f"{args.out} is not empty. Use a new folder.")
    images = sorted((args.folder / "img").glob("*.jpg"))[: args.count]
    if not images:
        raise ValueError(f"no receipts in {args.folder / 'img'}")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "reference.json").write_text(
        real_reference().model_dump_json(indent=1), encoding="utf-8"
    )
    manifest = {
        "seed": args.seed,
        "count": len(images),
        "config_version": settings.config_version,
        "source": "SROIE (ICDAR 2019) via github.com/zzzDavid/ICDAR-2019-SROIE",
    }
    (args.out / "set.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    for index, image in enumerate(images):
        key = json.loads((args.folder / "key" / f"{image.stem}.json").read_text(encoding="utf-8"))
        truth = parse_sroie_key(key)
        name = f"real_{args.seed}_{index:04d}"
        shutil.copyfile(image, args.out / f"{name}.jpg")
        claim = real_claim(args.seed, index, f"{name}.jpg", truth)
        (args.out / f"{name}.claim.json").write_text(
            claim.model_dump_json(indent=1), encoding="utf-8"
        )
        labels = {
            "claim_id": claim.claim_id,
            "should_pay": True,
            "correct_payout": 0,
            "defects": ["real_receipt"],
            "damage": "real",
            "duplicate_of": None,
            "source_receipt": image.stem,
            "truth": truth.model_dump(),
        }
        (args.out / f"{name}.truth.json").write_text(json.dumps(labels, indent=1), encoding="utf-8")
    logger.info("wrote %d real claims to %s", len(images), args.out)
    return 0


COMMANDS = {"read-sroie": read_sroie, "make-real-claims": make_real_claims}
