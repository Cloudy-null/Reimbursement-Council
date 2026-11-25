"""Commands for synthetic receipts: make a set of images with true values, and measure how well
the reader reads them back."""

import argparse
import json
import logging
import random
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from reimbursement_council.adapters.ocr_engine import CachedOcrEngine, EasyOcrEngine
from reimbursement_council.adapters.readers import make_reader_for
from reimbursement_council.adapters.receipt_drawing import DAMAGE_PRESETS, draw_receipt
from reimbursement_council.config.loader import load_settings
from reimbursement_council.core.extraction import extract_document
from reimbursement_council.core.models.claim import Document
from reimbursement_council.evaluation.reader_counts import reader_summary
from reimbursement_council.synthetic.accuracy import FIELDS, compare, summarize
from reimbursement_council.synthetic.receipt_content import ReceiptOptions, make_receipt_content

logger = logging.getLogger(__name__)

DAMAGE_MIX = ("none", "light", "light", "heavy")


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    make = commands.add_parser("make-receipts", help="Draw synthetic receipts with true values.")
    make.add_argument("--count", type=int, default=20)
    make.add_argument("--seed", type=int, default=1)
    make.add_argument("--out", type=Path, required=True)
    make.add_argument("--qr-share", type=float, default=0.7, help="Share of receipts with a QR.")
    make.add_argument("--damage", choices=["mixed", *DAMAGE_PRESETS], default="mixed")
    make.add_argument("--config-dir", type=Path, default=Path("config"))

    read = commands.add_parser("read-accuracy", help="Read a receipt set and score each field.")
    read.add_argument("folder", type=Path)
    read.add_argument("--reader", choices=["easyocr", "qr_only", "ollama"], default=None)
    read.add_argument("--config-dir", type=Path, default=Path("config"))
    read.add_argument("--ocr-cache", type=Path, default=Path("data/cache/ocr"))
    read.add_argument("--results-name", default="accuracy.json")
    read.add_argument("--two-readers", choices=["config", "on", "off"], default="config")


def make_receipts(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    args.out.mkdir(parents=True, exist_ok=True)
    for index in range(args.count):
        rng = random.Random(args.seed * 100_003 + index)
        options = ReceiptOptions(
            with_qr=rng.random() < args.qr_share,
            unlisted_item=rng.random() < 0.15,
        )
        content = make_receipt_content(rng, settings.prices, options, settings.policy.vat_rate)
        damage_name = rng.choice(DAMAGE_MIX) if args.damage == "mixed" else args.damage
        preset = DAMAGE_PRESETS[damage_name]
        damage = None if preset is None else preset.model_copy(update={"seed": index})
        if damage is not None and damage.rotate_degrees:
            damage = damage.model_copy(
                update={"rotate_degrees": damage.rotate_degrees * rng.choice((-1, 1))}
            )
        drawn = draw_receipt(content, damage)
        name = f"receipt_{args.seed}_{index:04d}"
        (args.out / f"{name}.png").write_bytes(drawn.png)
        truth = content.truth() | {"layout": content.layout, "damage": damage_name}
        (args.out / f"{name}.truth.json").write_text(
            json.dumps(truth, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    logger.info("wrote %d receipts to %s", args.count, args.out)
    return 0


def read_accuracy(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    changes: dict[str, object] = {}
    if args.reader:
        changes["reader"] = args.reader
    if args.two_readers != "config":
        changes["two_readers_enabled"] = args.two_readers == "on"
    decision = settings.decision.model_copy(update=changes)
    settings = settings.model_copy(update={"decision": decision})
    pick = make_reader_for(settings, CachedOcrEngine(EasyOcrEngine(), args.ocr_cache))
    rows = []
    counts: list[dict[str, int]] = []
    seconds: list[float] = []
    started = time.time()
    for image in sorted(args.folder.glob("*.png")):
        truth = json.loads(
            image.with_suffix("").with_suffix(".truth.json").read_text(encoding="utf-8")
        )
        document = Document(
            document_id=image.stem,
            claim_id=image.stem,
            kind="receipt",
            file_path=str(image),
            image_hash=None,
            uploaded_at=datetime.now(UTC),
        )
        read_started = time.perf_counter()
        reading = pick(document).read(document)
        seconds.append(time.perf_counter() - read_started)
        counts.append(reading.reader_counts)
        extraction = extract_document(document.document_id, reading, settings)
        row = compare(truth, extraction, qr_found=bool(reading.qr_payloads))
        row |= {"receipt": image.stem, "damage": truth["damage"], "layout": truth["layout"]}
        rows.append(row)
    summary = summarize(rows) | reader_summary(counts, seconds)
    by_damage = {
        name: summarize([row for row in rows if row["damage"] == name])
        for name in sorted({row["damage"] for row in rows})
    }
    report = {
        "reader": settings.decision.reader,
        "seconds": round(time.time() - started, 1),
        "summary": summary,
        "by_damage": by_damage,
        "by_layout": {
            name: summarize([row for row in rows if row["layout"] == name])
            for name in sorted({row["layout"] for row in rows})
        },
        "two_readers": settings.decision.two_readers_enabled,
        "rows": rows,
    }
    (args.folder / args.results_name).write_text(json.dumps(report, indent=1), encoding="utf-8")
    lines = [f"receipts: {summary['receipts']}  reader: {settings.decision.reader}"]
    lines += [f"{name:<16} {summary[name]:.3f}" for name in (*FIELDS, "item_codes")]
    sys.stdout.write("\n".join(lines) + "\n")
    return 0
