"""Friendly error pages: plain words and a way back, never a stack trace or raw JSON."""

import pytest
from fastapi.testclient import TestClient

from reimbursement_council.web.app import create_app
from reimbursement_council.web.context import WebContext


def test_a_missing_claim_gets_a_friendly_page(web: tuple[TestClient, WebContext]) -> None:
    client, _ = web
    response = client.get("/claims/no-such-claim")
    assert response.status_code == 404 and response.headers["content-type"].startswith("text/html")
    assert "could not find" in response.text and 'href="/' in response.text
    arabic = client.get("/claims/no-such-claim?lang=ar")
    assert 'dir="rtl"' in arabic.text and "لم نجد" in arabic.text


def test_a_bad_upload_gets_a_friendly_page(web: tuple[TestClient, WebContext]) -> None:
    client, _ = web
    response = client.post("/claims", data={"consent": "yes", "patient": "nobody"})
    assert response.status_code == 400 and "Pick a person" in response.text
    assert response.headers["content-type"].startswith("text/html")


def test_a_missing_form_field_is_a_400_page_not_raw_json(
    web: tuple[TestClient, WebContext],
) -> None:
    client, _ = web
    response = client.post("/claims", data={"consent": "yes"})
    assert response.status_code == 400 and response.headers["content-type"].startswith("text/html")


def test_the_api_keeps_json_errors(web: tuple[TestClient, WebContext]) -> None:
    client, _ = web
    response = client.get("/api/claims/no-such-claim/export")
    assert response.status_code == 404 and response.json() == {"detail": "No such claim."}


def test_a_server_error_gets_a_friendly_page_without_details(
    web: tuple[TestClient, WebContext], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, ctx = web

    def broken(*args: object) -> None:
        raise RuntimeError("database file is locked at C:/secret/path")

    monkeypatch.setattr(ctx.store, "list_decisions", broken)
    client = TestClient(create_app(ctx), raise_server_exceptions=False)
    response = client.get("/review")
    assert response.status_code == 500 and "Something went wrong" in response.text
    assert "secret" not in response.text and "Traceback" not in response.text
