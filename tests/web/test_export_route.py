"""GET /api/claims/{id}/export gives the claim export as JSON, valid against the schema."""

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
