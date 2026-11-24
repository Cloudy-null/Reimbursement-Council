"""GET /api/claims/{id}/export gives the claim export as JSON, valid against the schema."""

import pytest
from fastapi.testclient import TestClient

from reimbursement_council.adapters.export_schema import schema_errors
from reimbursement_council.web.context import WebContext
from tests.web.check_helpers import submit, upload


def test_export_of_a_sent_claim_is_valid_json(web: tuple[TestClient, WebContext]) -> None:
    client, _ = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"), ("p.png", b"prescription"))
    submit(client, claim_id)
    response = client.get(f"/api/claims/{claim_id}/export")
    assert response.status_code == 200 and response.headers["content-type"].startswith(
        "application/json"
    )
    data = response.json()
    assert data["claim_id"] == claim_id and schema_errors(data) == []
    assert len(data["documents"]) == 2


def test_download_asks_the_browser_to_save_a_file(web: tuple[TestClient, WebContext]) -> None:
    client, _ = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"))
    submit(client, claim_id)
    response = client.get(f"/api/claims/{claim_id}/export?download=1")
    assert f'filename="claim-{claim_id}.json"' in response.headers["content-disposition"]


def test_a_draft_or_unknown_claim_has_no_export(web: tuple[TestClient, WebContext]) -> None:
    client, _ = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"))
    assert client.get(f"/api/claims/{claim_id}/export").status_code == 409
    assert client.get("/api/claims/no-such-claim/export").status_code == 404


def test_result_page_and_review_card_link_to_the_download(
    web: tuple[TestClient, WebContext],
) -> None:
    client, _ = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"), ("p.png", b"prescription"))
    submit(client, claim_id)
    link = f"/api/claims/{claim_id}/export?download=1"
    assert link in client.get(f"/claims/{claim_id}").text
    assert link in client.get(f"/review/{claim_id}").text


def test_a_pdf_upload_is_kept_read_and_shown_as_an_image(
    web: tuple[TestClient, WebContext], monkeypatch: pytest.MonkeyPatch
) -> None:
    from reimbursement_council.adapters.receipt_drawing import draw_receipt
    from tests.adapters.test_pdf_input import as_pdf
    from tests.adapters.test_receipt_drawing import content
    from tests.web import check_helpers

    pdf = as_pdf(draw_receipt(content(5)).png)
    monkeypatch.setitem(check_helpers.READINGS, pdf, check_helpers.PHARMACY)
    client, ctx = web
    claim_id, response = upload(client, ("invoice.pdf", pdf))
    assert response.status_code == 303  # type: ignore[attr-defined]
    claim = ctx.store.load_claim(claim_id)
    assert claim is not None and claim.documents[0].file_path.endswith(".pdf")
    image = client.get(f"/claims/{claim_id}/documents/{claim.documents[0].document_id}")
    assert image.headers["content-type"] == "image/png" and image.content[:4] == b"\x89PNG"
