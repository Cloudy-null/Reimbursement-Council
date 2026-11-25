"""Consent step: documents are read only after the member agrees, and the time is kept."""

from fastapi.testclient import TestClient

from reimbursement_council.synthetic.claims import member_id
from reimbursement_council.web.context import WebContext


def test_no_consent_no_claim(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web
    response = client.post(
        "/claims",
        data={"patient": member_id(0)},
        files=[("photos", ("r.png", b"pharmacy", "image/png"))],
    )
    assert response.status_code == 400 and "agree" in response.text
    assert ctx.store.list_claims() == []


def test_consent_time_is_kept_on_the_claim(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web
    client.post(
        "/claims",
        data={"patient": member_id(0), "consent": "yes"},
        files=[("photos", ("r.png", b"pharmacy", "image/png"))],
    )
    (claim,) = ctx.store.list_claims()
    assert claim.consented_at is not None


def test_the_form_asks_for_consent_in_both_languages(web: tuple[TestClient, WebContext]) -> None:
    client, _ = web
    assert 'name="consent"' in client.get("/").text and "required" in client.get("/").text
    assert "أوافق" in client.get("/?lang=ar").text


def test_the_stylesheet_link_carries_the_file_version(web: tuple[TestClient, WebContext]) -> None:
    # A changed app.css gets a new URL, so a browser never keeps the old look (HANDOVER CHECK).
    from reimbursement_council.web.context import HERE, asset_version

    version = asset_version(HERE / "static" / "app.css")
    assert f"/static/app.css?v={version}" in web[0].get("/").text and len(version) == 10
