"""add-member: add a real person (with family and benefit usage so far) to the database the
website uses, so a claim can be tested for them.

reimbursement-council add-member --name "Sara Ahmed" --tier silver --used dental=600
"""

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.cli.data_dir import default_data_dir
from reimbursement_council.config.loader import load_settings
from reimbursement_council.core.dates import local_date_of
from reimbursement_council.core.new_member import NewMemberError, NewMemberForm, build_new_member
from reimbursement_council.web.i18n import text_for

logger = logging.getLogger(__name__)

EXIT_BAD_INPUT = 2


def web_database(data_dir: Path) -> Path:
    """The SQLite file `serve --data-dir` uses."""
    return data_dir / "web" / "claims.sqlite"


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    command = commands.add_parser("add-member", help="Add a person the website can claim for.")
    command.add_argument("--name", required=True, help="English display name.")
    command.add_argument("--name-ar", default="", help="Arabic name (optional).")
    command.add_argument("--tier", required=True, help="A tier in config/policy.yaml.")
    command.add_argument(
        "--dependant", action="append", default=[], help="A family member's name. Repeat it."
    )
    command.add_argument(
        "--used", action="append", default=[], help="BENEFIT=SAR used so far. Repeat it."
    )
    command.add_argument("--config-dir", type=Path, default=Path("config"))
    command.add_argument("--data-dir", type=Path, default=default_data_dir())


def _used(pairs: list[str]) -> dict[str, str]:
    used: dict[str, str] = {}
    for pair in pairs:
        key, separator, amount = pair.partition("=")
        if not separator:
            raise ValueError(f"--used must look like dental=600, got {pair!r}")
        used[key.strip()] = amount
    return used


def add_member(args: argparse.Namespace) -> int:
    settings = load_settings(args.config_dir)
    form = NewMemberForm(
        name=args.name,
        name_ar=args.name_ar,
        tier=args.tier,
        dependants=tuple(args.dependant),
        used=_used(args.used),
    )
    now = datetime.now(UTC)
    today = local_date_of(now, settings.policy.local_utc_offset_hours)
    try:
        added = build_new_member(form, settings.policy, today, lambda: str(uuid4()))
    except NewMemberError as error:
        text = text_for("en")
        for field, code in error.errors.items():
            logger.error("%s: %s", field, text[code])
        return EXIT_BAD_INPUT
    ClaimStore(web_database(args.data_dir)).save_new_member(added, now)
    sys.stdout.write(f"{added.members[0].member_id}\n")
    return 0


COMMANDS = {"add-member": add_member}
