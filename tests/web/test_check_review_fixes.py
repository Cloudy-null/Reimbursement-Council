"""Fixes from the Task 13 review: guards on /fix, file names, refusals, kept choices."""

from fastapi.testclient import TestClient

from reimbursement_council.core.models.decision import SelfFixRequest
from reimbursement_council.synthetic.claims import member_id
from reimbursement_council.web.context import WebContext
from tests.web.check_helpers import submit, upload

PHOTO = ("photos", ("r2.png", b"pharmacy", "image/png"))


def sent_claim(web: tuple[TestClient, WebContext], lane: str = "self_fix") -> str:
    """A submitted pharmacy claim with a prescription, its decision set to the given lane."""
    client, ctx = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"), ("p.png", b"prescription"))
    submit(client, claim_id)
    decision = ctx.store.load_decision(claim_id)
    assert decision is not None
    request = (
        SelfFixRequest(kind="check_photo", field="total", text="t") if lane == "self_fix" else None
    )
    ctx.store.save_decision(decision.model_copy(update={"lane": lane, "self_fix_request": request}))
    return claim_id


def test_fix_is_refused_unless_the_claim_waits_for_a_self_fix(
    web: tuple[TestClient, WebContext],
) -> None:
    client, ctx = web
    approved = sent_claim(web, lane="auto_approve")
    assert client.post(f"/claims/{approved}/fix", files=[PHOTO]).status_code == 409
    draft, _ = upload(client, ("r.png", b"pharmacy"))
    assert client.post(f"/claims/{draft}/fix", files=[PHOTO]).status_code == 409
    claim = ctx.store.load_claim(approved)
    assert claim is not None and claim.status == "submitted" and claim.retries_used == 0


def test_fix_is_refused_when_no_retries_are_left(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web
    claim_id = sent_claim(web)
    claim = ctx.store.load_claim(claim_id)
    assert claim is not None
    used = ctx.settings.decision.self_fix_max_retries
    ctx.store.save_claim(claim.model_copy(update={"retries_used": used}))
    assert client.post(f"/claims/{claim_id}/fix", files=[PHOTO]).status_code == 409


def test_every_document_gets_its_own_file(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web
    claim_id = sent_claim(web)
    claim = ctx.store.load_claim(claim_id)
    assert claim is not None
    second = claim.documents[1].document_id
    client.post(f"/claims/{claim_id}/fix", files=[PHOTO], data={"replace": second})
    client.post(f"/claims/{claim_id}/documents", files=[PHOTO])
    claim = ctx.store.load_claim(claim_id)
    assert claim is not None and len(claim.documents) == 3
    assert len({d.file_path for d in claim.documents}) == 3


def test_fix_with_only_refused_files_changes_nothing(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web
    claim_id = sent_claim(web)
    before = ctx.store.load_claim(claim_id)
    assert before is not None
    response = client.post(
        f"/claims/{claim_id}/fix",
        files=[("photos", ("x.gif", b"GIF89a", "image/gif"))],
        data={"replace": before.documents[1].document_id},
    )
    assert response.status_code == 400 and "x.gif" in response.text
    assert ctx.store.load_claim(claim_id) == before


def test_a_field_error_keeps_the_chosen_kind_and_category(
    web: tuple[TestClient, WebContext],
) -> None:
    client, ctx = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"), ("p.png", b"prescription"))
    claim = ctx.store.load_claim(claim_id)
    assert claim is not None
    second = claim.documents[1].document_id
    response = submit(
        client,
        claim_id,
        field_total="12,50x",
        category="dental",
        **{f"kind_{second}": "medical_report"},
    )
    assert response.status_code == 400  # type: ignore[attr-defined]
    assert '<option value="medical_report" selected>' in response.text  # type: ignore[attr-defined]
    assert '<option value="dental" selected>' in response.text  # type: ignore[attr-defined]


def test_refusal_reasons_are_in_the_page_language(web: tuple[TestClient, WebContext]) -> None:
    client, _ = web
    response = client.post(
        "/claims",
        data={"patient": member_id(0), "lang": "ar"},
        files=[
            ("photos", ("r.png", b"pharmacy", "image/png")),
            ("photos", ("notes.gif", b"GIF89a", "image/gif")),
        ],
    )
    assert "notes.gif" in response.text and "not a PNG" not in response.text


def test_fix_form_names_each_document_by_its_type(web: tuple[TestClient, WebContext]) -> None:
    client, _ = web
    claim_id = sent_claim(web)
    page = client.get(f"/claims/{claim_id}?lang=ar").text
    assert "2. وصفة طبية" in page and "2. prescription" not in page
