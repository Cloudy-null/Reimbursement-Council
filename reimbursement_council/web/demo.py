"""Demo mode: the five demo claims as files, and a warm-up so the demo never waits.

The files are drawn once per day (dated three days ago, so they are inside the claim window)
into samples/demo/<date>/<claim>/. The warm-up loads the OCR model and reads every demo file
once, so the readings are in the OCR cache before anyone clicks: no wait and no internet.
"""

import io
import logging
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image

from reimbursement_council.adapters.document_drawing import draw_clinical_document
from reimbursement_council.adapters.receipt_drawing import draw_receipt
from reimbursement_council.core.models.claim import Document
from reimbursement_council.synthetic.demo_claims import DemoFile, demo_claims, demo_fixes
from reimbursement_council.web.context import WebContext

logger = logging.getLogger(__name__)

DEMO_NAMES = ("approve", "missing", "mismatch", "edit", "pdf")
WARM_UP_DONE = threading.Event()  # GET /api/ready says when the demo files are read


def _png(file: DemoFile) -> bytes:
    if file.receipt is not None:
        return draw_receipt(file.receipt).png
    if file.clinical is not None:
        return draw_clinical_document(file.clinical).png
    raise ValueError(f"demo file {file.file_name} has nothing to draw")


def _pdf(png: bytes) -> bytes:
    buffer = io.BytesIO()
    Image.open(io.BytesIO(png)).convert("RGB").save(buffer, format="PDF", resolution=72)
    return buffer.getvalue()


def demo_folder(ctx: WebContext) -> Path:
    day = (datetime.now(UTC) + timedelta(hours=ctx.settings.policy.local_utc_offset_hours)).date()
    return ctx.samples / "demo" / day.isoformat()


def _issued(folder: Path) -> datetime:
    return (datetime.fromisoformat(folder.name) - timedelta(days=3)).replace(hour=10, minute=30)


def _write(folder: Path, files: dict[str, list[DemoFile]]) -> dict[str, list[Path]]:
    paths: dict[str, list[Path]] = {}
    for name, demo_files in files.items():
        paths[name] = []
        for file in demo_files:
            path = folder / name / file.file_name
            if not path.is_file():
                path.parent.mkdir(parents=True, exist_ok=True)
                png = _png(file)
                path.write_bytes(_pdf(png) if file.as_pdf else png)
            paths[name].append(path)
    return paths


def ensure_demo_files(ctx: WebContext) -> dict[str, list[Path]]:
    """Every demo claim's files, drawn if today's are not there yet."""
    folder = demo_folder(ctx)
    claims = demo_claims(_issued(folder), ctx.settings.prices, ctx.settings.policy.vat_rate)
    return _write(folder, {name: claims[name] for name in DEMO_NAMES})


def ensure_demo_fix_files(ctx: WebContext) -> dict[str, list[Path]]:
    """Files to send in the fix step of a demo (in <claim>/fix/)."""
    folder = demo_folder(ctx)
    fixes = demo_fixes(_issued(folder), ctx.settings.prices)
    return _write(folder, {f"{name}/fix": files for name, files in fixes.items()})


def warm_up(ctx: WebContext) -> None:
    """Read every demo file once (this also loads the OCR model). Errors are only logged: a
    failed warm-up makes the first demo slower, never broken."""
    try:
        _read_every_demo_file(ctx)
    except Exception:  # never leave /api/ready waiting; the first demo is just slower
        logger.exception("warm-up stopped early")
    finally:
        WARM_UP_DONE.set()
    logger.info("warm-up done: demo files are read and cached")


def _read_every_demo_file(ctx: WebContext) -> None:
    every = ensure_demo_files(ctx) | ensure_demo_fix_files(ctx)
    for name, paths in every.items():
        for path in paths:
            document = Document(
                document_id=f"warm-{name.replace('/', '-')}-{path.stem}",
                claim_id="warm-up",
                kind="other",
                file_path=str(path),
                image_hash=None,
                uploaded_at=datetime.now(UTC),
            )
            try:
                ctx.reader_for(document).read(document)
            except (ValueError, OSError) as error:
                logger.warning("warm-up could not read demo file %s: %s", path.name, error)


_started = threading.Event()


def warming() -> bool:
    """A warm-up was started and has not finished."""
    return _started.is_set() and not WARM_UP_DONE.is_set()


def start_warm_up(ctx: WebContext) -> threading.Thread:
    WARM_UP_DONE.clear()
    _started.set()
    thread = threading.Thread(target=warm_up, args=(ctx,), name="demo-warm-up", daemon=True)
    thread.start()
    return thread
