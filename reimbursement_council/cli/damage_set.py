"""make-damage-set: copies of a claim set with each kind of photo damage at levels 1 to 5,
in folders like OUT/blur_3/. Strengths are in config/synthetic.yaml (damage_suite)."""

import argparse
import logging
from pathlib import Path

from reimbursement_council.adapters.damage_suite import MAX_LEVEL
from reimbursement_council.adapters.damaged_sets import read_claims, write_damaged_set
from reimbursement_council.cli.sheet_sets import ensure_empty
from reimbursement_council.config.loader import load_settings

logger = logging.getLogger(__name__)


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    make = commands.add_parser(
        "make-damage-set", help="Copy a claim set once per damage kind and level (1 to 5)."
    )
    make.add_argument("source", type=Path, help="A set made by make-claims or a sheet set.")
    make.add_argument("out", type=Path, help="A new, empty folder.")
    make.add_argument("--kinds", default="all", help="Comma separated kinds, or all.")
    make.add_argument("--levels", default="1,2,3,4,5", help="Comma separated levels, 1 to 5.")
    make.add_argument("--config-dir", type=Path, default=Path("config"))


def make_damage_set(args: argparse.Namespace) -> int:
    suite = load_settings(args.config_dir).synthetic.damage_suite
    kinds = list(suite) if args.kinds == "all" else args.kinds.split(",")
    unknown = [kind for kind in kinds if kind not in suite]
    if unknown:
        raise ValueError(f"no strengths in synthetic.yaml damage_suite for {unknown}")
    levels = [int(level) for level in args.levels.split(",")]
    if any(not 1 <= level <= MAX_LEVEL for level in levels):
        raise ValueError(f"levels must be 1 to {MAX_LEVEL}, got {levels}")
    read_claims(args.source)  # check the source before writing anything
    ensure_empty(args.out)
    for kind in kinds:
        for level in levels:
            count = write_damaged_set(
                args.source, args.out / f"{kind}_{level}", kind, level, suite[kind]
            )
            logger.info("wrote %s level %d: %d claims", kind, level, count)
    return 0


COMMANDS = {"make-damage-set": make_damage_set}
