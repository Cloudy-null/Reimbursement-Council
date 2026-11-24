"""Command line entrypoint. Thin: load inputs, call the pipeline, print the result.

reimbursement-council run-claim CLAIM_PATH --reference REFERENCE_PATH
"""

import argparse
import io
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from reimbursement_council.adapters.files import load_claim_file, load_reference_file
from reimbursement_council.adapters.log_privacy import mask_all_logs
from reimbursement_council.adapters.ocr_engine import (
    CachedOcrEngine,
    EasyOcrEngine,
    OcrNotInstalledError,
)
from reimbursement_council.adapters.readers import make_reader_for
from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.cli import claims_set, export, real, receipts
from reimbursement_council.config.loader import ConfigError, load_settings
from reimbursement_council.core.models.decision import Decision
from reimbursement_council.core.money import format_sar
from reimbursement_council.pipeline.process_claim import process_claim

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_BAD_INPUT = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reimbursement-council",
        description="Decide health insurance reimbursement claims.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run_claim = commands.add_parser("run-claim", help="Decide one claim file and print the result.")
    run_claim.add_argument("claim_path", type=Path, help="A *.claim.json file.")
    run_claim.add_argument("--reference", type=Path, required=True, help="Members and policies.")
    run_claim.add_argument("--config-dir", type=Path, default=Path("config"))
    run_claim.add_argument("--db", type=Path, default=Path("data/claims.sqlite"))
    run_claim.add_argument("--ocr-cache", type=Path, default=Path("data/cache/ocr"))
    receipts.add_commands(commands)
    claims_set.add_commands(commands)
    export.add_commands(commands)
    real.add_commands(commands)
    serve = commands.add_parser("serve", help="Start the website on this computer.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--config-dir", type=Path, default=Path("config"))
    serve.add_argument("--data-dir", type=Path, default=Path("data"))
    serve.add_argument("--reader", choices=["easyocr", "qr_only"], default=None)
    return parser


def _summary(decision: Decision) -> str:
    if decision.lane == "auto_reject":
        payout = "none (rejected)"
    elif decision.payout_calculated is None:
        payout = "none"
    else:
        payout = f"{format_sar(decision.payout_calculated)} SAR"
    lines = [
        f"claim: {decision.claim_id}",
        f"lane: {decision.lane}",
        f"outcome: {decision.outcome}",
        f"payout: {payout}",
        f"reason: {decision.lane_reason}",
        f"message (en): {decision.member_message.en}",
        f"message (ar): {decision.member_message.ar}",
    ]
    return "\n".join(lines) + "\n"


def _use_utf8_stdout() -> None:
    """Arabic text must print even when stdout is redirected on Windows."""
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")


def _serve(args: argparse.Namespace) -> int:
    """Run the website with uvicorn. Demo people come from the synthetic set (seed 7)."""
    import uvicorn

    from reimbursement_council.synthetic.claims import make_claim_set
    from reimbursement_council.web.app import WebContext, create_app

    settings = load_settings(args.config_dir)
    if args.reader:
        decision = settings.decision.model_copy(update={"reader": args.reader})
        settings = settings.model_copy(update={"decision": decision})
    engine = CachedOcrEngine(EasyOcrEngine(), args.data_dir / "cache" / "ocr")
    context = WebContext(
        settings=settings,
        reference=make_claim_set(7, 0, settings).reference,
        store=ClaimStore(args.data_dir / "web" / "claims.sqlite"),
        reader_for=make_reader_for(settings, engine),
        uploads=args.data_dir / "web" / "uploads",
        samples=args.data_dir / "web" / "samples",
        results_root=args.data_dir,
    )
    uvicorn.run(create_app(context), host=args.host, port=args.port)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s"
    )
    mask_all_logs()  # no personal data in logs (brief: data sensitivity)
    args = _parser().parse_args(argv)
    commands = {
        "make-receipts": receipts.make_receipts,
        "read-accuracy": receipts.read_accuracy,
        "make-claims": claims_set.make_claims,
        "run-set": claims_set.run_set,
        "fit-calibration": claims_set.fit_calibration,
        "serve": _serve,
        **export.COMMANDS,
        **real.COMMANDS,
    }
    if args.command in commands:
        command = commands[args.command]
        _use_utf8_stdout()
        try:
            return command(args)
        except (ConfigError, ValueError, OcrNotInstalledError, FileNotFoundError) as error:
            logger.error("command failed: %s", error)
            return EXIT_BAD_INPUT
    try:
        settings = load_settings(args.config_dir)
        reference = load_reference_file(args.reference)
        claim = load_claim_file(args.claim_path)
        engine = CachedOcrEngine(EasyOcrEngine(), args.ocr_cache)
        decision = process_claim(
            claim,
            reference,
            settings,
            ClaimStore(args.db),
            datetime.now(UTC),
            reader_for=make_reader_for(settings, engine),
        )
    except (ConfigError, LookupError, FileNotFoundError, ValueError, OcrNotInstalledError) as error:
        # pydantic's ValidationError is a ValueError, so bad files land here too.
        logger.error("could not decide the claim: %s", error)
        return EXIT_BAD_INPUT
    _use_utf8_stdout()
    sys.stdout.write(_summary(decision))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
