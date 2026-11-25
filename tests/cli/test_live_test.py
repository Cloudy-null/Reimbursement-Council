"""live-test against a real running website (uvicorn in a thread, fake reader)."""

import argparse
import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn
from PIL import Image

from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.adapters.web_client import WebClient, WebClientError
from reimbursement_council.cli.live_test import claims_in, live_test
from reimbursement_council.core.models.claim import Document, ReaderOutput
from reimbursement_council.evaluation.live_report import live_summary
from reimbursement_council.synthetic.claims import make_claim_set
from reimbursement_council.web.app import create_app
from reimbursement_council.web.context import WebContext
from tests.factories import settings_with


class BlankReader:
    """Reads nothing, like a photo with no text: the claim must still go through every step."""

    def read(self, document: Document) -> ReaderOutput:
        return ReaderOutput(fields=[], line_items=[], qr_payloads=[])


@pytest.fixture
def site(tmp_path: Path) -> Iterator[str]:
    settings = settings_with(reader="qr_only")
    ctx = WebContext(
        settings=settings,
        reference=make_claim_set(7, 0, settings).reference,
        store=ClaimStore(tmp_path / "web.sqlite"),
        reader_for=lambda document: BlankReader(),
        uploads=tmp_path / "uploads",
        samples=tmp_path / "samples",
        results_root=tmp_path / "results",
    )
    server = uvicorn.Server(uvicorn.Config(create_app(ctx), port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def test_claims_in_takes_files_and_subfolders(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("skip")
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "receipt.png").write_bytes(b"x")
    (tmp_path / "b" / "report.pdf").write_bytes(b"x")
    (tmp_path / "empty").mkdir()
    found = [(name, [p.name for p in paths]) for name, paths in claims_in(tmp_path)]
    assert found == [("a", ["a.jpg"]), ("b", ["receipt.png", "report.pdf"])]


def test_live_test_runs_the_whole_member_path_and_writes_a_report(
    site: str, tmp_path: Path
) -> None:
    photos = tmp_path / "photos"
    photos.mkdir()
    Image.new("RGB", (40, 40), "white").save(photos / "one.png")
    out = tmp_path / "out"
    args = argparse.Namespace(
        folder=photos, url=site, lang="ar", patient=None, out=out, timeout=60.0
    )
    assert live_test(args) == 0
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    record = report["claims"][0]
    assert record["error"] is None
    assert record["lane"] in {"auto_approve", "auto_reject", "self_fix", "human_review"}
    assert record["schema_valid"] is True
    assert record["seconds"]["total"] >= record["seconds"]["upload_and_read"] > 0
    assert report["summary"]["finished"] == 1
    assert (out / "one.export.json").is_file()


def test_an_unreachable_site_is_a_clear_error() -> None:
    with pytest.raises(WebClientError):
        WebClient("http://127.0.0.1:9", timeout=2).first_patient()


def test_summary_counts_errors_apart() -> None:
    done = {"error": None, "lane": "self_fix", "seconds": {"total": 2.0}, "schema_valid": True}
    failed = {"error": "boom", "lane": None, "seconds": {"total": 1.0}}
    summary = live_summary([done, failed])
    assert summary["errors"] == 1 and summary["finished"] == 1
    assert summary["seconds_per_claim_mean"] == 2.0
