"""make-language-set: receipts in each language and script, in the make-receipts file format
(receipt_SEED_NNNN.png and .truth.json), so read-accuracy can score them. Each truth also says
the receipt's language and whether we support it; read-accuracy groups by language (layout)."""

import argparse
import json
import logging
import random
from pathlib import Path

from reimbursement_council.adapters.receipt_drawing import draw_receipt
from reimbursement_council.adapters.sheet_drawing import draw_sheet
from reimbursement_council.cli.sheet_sets import ensure_empty
from reimbursement_council.config.loader import load_settings
from reimbursement_council.synthetic.language_content import (
    LANGUAGES,
    SUPPORTED,
    make_language_receipt,
)

logger = logging.getLogger(__name__)


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    make = commands.add_parser(
        "make-language-set", help="Draw receipts in each language, with true values."
    )
    make.add_argument("out", type=Path, help="A new, empty folder.")
    make.add_argument("--seed", type=int, default=1)
    make.add_argument("--per-language", type=int, default=6)
    make.add_argument("--config-dir", type=Path, default=Path("config"))


def make_language_set(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    ensure_empty(args.out)
    args.out.mkdir(parents=True, exist_ok=True)
    index = 0
    for language in LANGUAGES:
        for _ in range(args.per_language):
            rng = random.Random(args.seed * 400_009 + index)
            receipt = make_language_receipt(rng, language, settings)
            drawn = (
                draw_receipt(receipt.content)
                if receipt.sheet is None
                else draw_sheet(receipt.sheet)
            )
            name = f"receipt_{args.seed}_{index:04d}"
            (args.out / f"{name}.png").write_bytes(drawn.png)
            (args.out / f"{name}.truth.json").write_text(
                json.dumps(receipt.truth(), ensure_ascii=False, indent=1), encoding="utf-8"
            )
            index += 1
    manifest = {
        "seed": args.seed,
        "count": index,
        "label": "synthetic language samples",
        "languages": {name: SUPPORTED[name] for name in LANGUAGES},
        "config_version": settings.config_version,
    }
    (args.out / "set.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    logger.info("wrote %d receipts in %d languages to %s", index, len(LANGUAGES), args.out)
    return 0


COMMANDS = {"make-language-set": make_language_set}
