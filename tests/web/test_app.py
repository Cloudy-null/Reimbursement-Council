import json
import random
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from reimbursement_council.adapters.readers import make_reader_for
from reimbursement_council.adapters.receipt_drawing import draw_receipt
from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.synthetic.claims import make_claim_set, member_id
from reimbursement_council.synthetic.receipt_content import ReceiptOptions, make_receipt_content
from reimbursement_council.web.app import WebContext, create_app
from tests.adapters.test_ocr_reader import FakeEngine
from tests.factories import settings_with


@pytest.fixture
def web(tmp_path: Path) -> tuple[TestClient, WebContext]:
    settings = settings_with(reader="qr_only")
    ctx = WebContext(
        settings=settings,
        reference=make_claim_set(7, 0, settings).reference,
        store=ClaimStore(tmp_path / "web.sqlite"),
        reader_for=make_reader_for(settings, FakeEngine([])),
        uploads=tmp_path / "uploads",
        samples=tmp_path / "samples",
        results_root=tmp_path / "results",
    )
    return TestClient(create_app(ctx)), ctx


def send_sample(client: TestClient, patient: int = 0, lang: str = "en") -> str:
    response = client.post(
        "/claims",
        data={"patient": member_id(patient), "sample": "clinic", "lang": lang},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return response.headers["location"].split("/claims/")[1].split("?")[0]


def png() -> bytes:
    s = settings_with()
    content = make_receipt_content(random.Random(3), s.prices, ReceiptOptions(), s.policy.vat_rate)
    return draw_receipt(content).png


def test_home_lists_people_and_samples_in_both_languages(
    web: tuple[TestClient, WebContext],
) -> None:
    client, _ = web
    english = client.get("/").text
    assert "Sara Ahmed" in english and "/samples/clinic.png" in english and 'dir="ltr"' in english
    arabic = client.get("/?lang=ar").text
    assert 'dir="rtl"' in arabic and "مطالبة جديدة" in arabic
    assert client.get("/samples/clinic.png").status_code == 200
    assert client.get("/samples/nothing.png").status_code == 404


def test_sample_claim_is_decided_and_shown(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web
    claim_id = send_sample(client)
    decision = ctx.store.load_decision(claim_id)
    assert decision is not None
    page = client.get(f"/claims/{claim_id}").text
    assert decision.member_message.en in page
    assert client.get(f"/claims/{claim_id}/document").status_code == 200
    assert client.get("/claims/missing").status_code == 404


def test_uploaded_photo_and_bad_inputs(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web
    ok = client.post(
        "/claims",
        data={"patient": member_id(1)},
        files={"photo": ("r.png", png(), "image/png")},
        follow_redirects=False,
    )
    assert ok.status_code == 303
    gif = client.post(
        "/claims",
        data={"patient": member_id(1)},
        files={"photo": ("r.gif", b"GIF89a", "image/gif")},
    )
    assert gif.status_code == 400
    assert client.post("/claims", data={"patient": "nobody", "sample": "clinic"}).status_code == 400
    assert client.post("/claims", data={"patient": member_id(1)}).status_code == 400


def test_reviewer_flow(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web
    claim_id = send_sample(client)
    client.post(f"/claims/{claim_id}/to-reviewer", data={"lang": "en"})
    assert claim_id in client.get("/review").text
    card = client.get(f"/review/{claim_id}").text
    assert "document_checker" in card and "Decide" in card
    bad = client.post(
        f"/review/{claim_id}",
        data={"action": "approve_amount", "amount": "abc", "opened": "2026-11-24T01:00:00+00:00"},
    )
    assert bad.status_code == 400
    saved = client.post(
        f"/review/{claim_id}",
        data={
            "action": "approve_amount",
            "amount": "120.00",
            "reason": "network price",
            "opened": "2026-11-24T01:00:00+00:00",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    review = ctx.store.load_review(claim_id)
    assert review is not None and review.amount == 12000
    assert claim_id not in client.get("/review").text


def test_self_fix_resend_counts_a_retry(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web
    claim_id = send_sample(client)
    response = client.post(
        f"/claims/{claim_id}/fix",
        data={"lang": "en"},
        files={"photo": ("again.png", png(), "image/png")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    claim = ctx.store.load_claim(claim_id)
    assert claim is not None and claim.retries_used == 1


def test_numbers_page_reads_harness_results(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web
    assert "No runs found" in client.get("/metrics").text
    folder = ctx.results_root / "check"
    folder.mkdir(parents=True)
    metrics = {
        "claims": 60,
        "automation_rate": 0.55,
        "auto_approve_precision": 0.97,
        "payable_recall": 0.5,
        "false_reject_rate": 0.0,
        "reviews_per_1000": 300.0,
        "ece": 0.08,
        "total_cost_sar": 512.0,
    }
    (folder / "results.json").write_text(
        json.dumps({"reader": "easyocr", "calibration": False, "metrics": metrics, "rows": []}),
        encoding="utf-8",
    )
    page = client.get("/metrics").text
    assert "0.97" in page and "easyocr" in page
