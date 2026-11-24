"""Demo mode: five ready demo claims, and a warm-up that reads them before anyone clicks."""

import dataclasses
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from reimbursement_council.core.models.claim import Document, ReaderOutput
from reimbursement_council.synthetic.claims import member_id
from reimbursement_council.web.app import create_app
from reimbursement_council.web.context import WebContext
from reimbursement_council.web.demo import DEMO_NAMES, ensure_demo_files, warm_up


class CountingReader:
    def __init__(self, seen: list[str]) -> None:
        self.seen = seen

    def read(self, document: Document) -> ReaderOutput:
        self.seen.append(document.file_path)
        return ReaderOutput(fields=[], line_items=[], qr_payloads=[])


def test_five_demo_claims_with_their_documents(web: tuple[TestClient, WebContext]) -> None:
    _, ctx = web
    files = ensure_demo_files(ctx)
    assert tuple(files) == DEMO_NAMES
    assert [len(files[n]) for n in DEMO_NAMES] == [1, 1, 2, 2, 1]
    assert files["pdf"][0].read_bytes()[:5] == b"%PDF-"
    assert all(p.read_bytes()[:4] == b"\x89PNG" for n in DEMO_NAMES[:4] for p in files[n])
    assert ensure_demo_files(ctx) == files  # drawn once a day, then reused


def test_demo_dates_are_inside_the_claim_window(web: tuple[TestClient, WebContext]) -> None:
    from reimbursement_council.synthetic.demo_claims import demo_claims

    issued = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=3)
    claims = demo_claims(issued, web[1].settings.prices, 0.15)
    receipts = [f.receipt for files in claims.values() for f in files if f.receipt]
    assert receipts and all(r.issued_at == issued for r in receipts)


def test_a_demo_button_starts_a_draft_with_all_its_documents(
    web: tuple[TestClient, WebContext],
) -> None:
    _, ctx = web
    quiet = dataclasses.replace(ctx, reader_for=lambda d: CountingReader([]))
    client = TestClient(create_app(quiet))
    assert 'name="demo" value="mismatch"' in client.get("/").text
    response = client.post(
        "/claims",
        data={"consent": "yes", "patient": member_id(0), "demo": "mismatch"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    (claim,) = ctx.store.list_claims()
    assert len(claim.documents) == 2
    assert (
        client.post(
            "/claims", data={"consent": "yes", "patient": member_id(0), "demo": "x"}
        ).status_code
        == 400
    )


def test_warm_up_reads_every_demo_file_once(web: tuple[TestClient, WebContext]) -> None:
    _, ctx = web
    seen: list[str] = []
    warm_up(dataclasses.replace(ctx, reader_for=lambda d: CountingReader(seen)))
    assert len(seen) == sum(len(p) for p in ensure_demo_files(ctx).values()) == 7
