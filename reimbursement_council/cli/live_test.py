"""live-test: send real photos through the running website, as a member would, and time it.

Each file in the folder is one claim; each subfolder is one claim with all its files (for
example a receipt and a medical report). For each claim: upload with consent, send the check
step as it is, fetch the export and check it against the schema. Writes report.json and one
export per claim. The photos are never copied into git (data/ and outputs/ are ignored).
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from reimbursement_council.adapters.export_schema import load_schema, schema_errors
from reimbursement_council.adapters.web_client import WebClient, WebClientError
from reimbursement_council.evaluation.live_report import claim_record, failed_record, live_summary

logger = logging.getLogger(__name__)

PHOTO_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".pdf"})


def add_commands(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    live = commands.add_parser(
        "live-test", help="Send real photos through the running website and time each claim."
    )
    live.add_argument("folder", type=Path)
    live.add_argument("--url", default="http://127.0.0.1:8000")
    live.add_argument("--lang", choices=["ar", "en"], default="ar")
    live.add_argument("--patient", default=None, help="Member id; default: first on the page.")
    live.add_argument("--out", type=Path, default=Path("outputs/live_test"))
    live.add_argument("--timeout", type=float, default=600.0)
    live.add_argument(
        "--keep-exports",
        action="store_true",
        help="Also write each claim's full export (holds personal data; keep it out of git).",
    )


def claims_in(folder: Path) -> list[tuple[str, list[Path]]]:
    """One claim per photo file, and one per subfolder holding photos."""
    claims: list[tuple[str, list[Path]]] = []
    for entry in sorted(folder.iterdir()):
        if entry.is_file() and entry.suffix.lower() in PHOTO_SUFFIXES:
            claims.append((entry.stem, [entry]))
        elif entry.is_dir():
            photos = sorted(p for p in entry.iterdir() if p.suffix.lower() in PHOTO_SUFFIXES)
            if photos:
                claims.append((entry.name, photos))
    return claims


def _one_claim(
    client: WebClient,
    patient: str,
    name: str,
    paths: list[Path],
    lang: str,
    out: Path,
    keep_export: bool,
) -> dict[str, Any]:
    files = [p.name for p in paths]
    seconds: dict[str, float] = {}
    started = time.perf_counter()
    try:
        claim_id = client.upload(patient, [(p.name, p.read_bytes()) for p in paths], lang)
        seconds["upload_and_read"] = time.perf_counter() - started
        step = time.perf_counter()
        client.submit(claim_id, lang)
        seconds["send_and_decide"] = time.perf_counter() - step
        seconds["total"] = time.perf_counter() - started
        export = client.export(claim_id)
    except WebClientError as error:
        seconds["total"] = time.perf_counter() - started
        logger.warning("live claim %s failed: %s", name, error)
        return failed_record(name, files, seconds, str(error))
    if keep_export:
        (out / f"{name}.export.json").write_text(json.dumps(export, indent=1), encoding="utf-8")
    errors = schema_errors(export, load_schema())
    return claim_record(name, files, export, seconds, errors)


def live_test(args: argparse.Namespace) -> int:
    claims = claims_in(args.folder)
    if not claims:
        raise ValueError(f"no photos in {args.folder}: put photos or subfolders of photos there")
    client = WebClient(args.url, args.timeout)
    patient = args.patient or client.first_patient()
    args.out.mkdir(parents=True, exist_ok=True)
    records = []
    for number, (name, paths) in enumerate(claims, start=1):
        logger.info("live claim %d/%d %s: %d file(s)", number, len(claims), name, len(paths))
        records.append(
            _one_claim(client, patient, name, paths, args.lang, args.out, args.keep_exports)
        )
    report = {
        "url": args.url,
        "lang": args.lang,
        "summary": live_summary(records),
        "claims": records,
    }
    (args.out / "report.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    lines = [f"{k:<34} {v}" for k, v in report["summary"].items()]
    lines += [
        f"{r['name']:<24} {r.get('lane')!s:<13} {r['seconds'].get('total', 0):>7.1f} s  "
        f"{r.get('error') or r.get('asked_member') or ''}"
        for r in records
    ]
    sys.stdout.write("\n".join(lines) + "\n")
    return 0
