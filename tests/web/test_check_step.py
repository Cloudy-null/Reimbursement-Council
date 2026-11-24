"""Task 13: upload one or more documents, check what was read, then submit (spec 6.5)."""

from fastapi.testclient import TestClient

from reimbursement_council.core.models.decision import SelfFixRequest
from reimbursement_council.synthetic.claims import member_id
from reimbursement_council.web.context import WebContext
from tests.web.check_helpers import submit, upload


def test_upload_saves_a_draft_and_shows_the_check_page(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web
    claim_id, response = upload(client, ("r.png", b"pharmacy"))
    assert response.status_code == 303  # type: ignore[attr-defined]
    assert response.headers["location"].startswith(f"/claims/{claim_id}/check")  # type: ignore[attr-defined]
    claim = ctx.store.load_claim(claim_id)
    assert claim is not None and claim.status == "draft"
    assert ctx.store.load_decision(claim_id) is None
    assert len(ctx.store.load_readings(claim_id)) == 1
    page = client.get(f"/claims/{claim_id}/check").text
    assert "Sara Ahmed" in page and "17.25" in page


def test_check_page_lists_the_missing_prescription_for_a_pharmacy_receipt(
    web: tuple[TestClient, WebContext],
) -> None:
    client, _ = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"))
    page = client.get(f"/claims/{claim_id}/check").text
    assert "prescription" in page and f"/claims/{claim_id}/documents" in page
    arabic = client.get(f"/claims/{claim_id}/check?lang=ar").text
    assert "وصفة طبية" in arabic and 'dir="rtl"' in arabic


def test_submit_with_an_unchanged_form_makes_no_edits(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"))
    response = submit(client, claim_id)
    assert response.status_code == 303  # type: ignore[attr-defined]
    claim = ctx.store.load_claim(claim_id)
    decision = ctx.store.load_decision(claim_id)
    assert claim is not None and claim.edits == [] and claim.status == "submitted"
    assert decision is not None and decision.lane == "self_fix"
    assert decision.self_fix_request is not None
    assert decision.self_fix_request.kind == "add_document"


def test_submit_with_a_changed_total_records_a_field_edit(
    web: tuple[TestClient, WebContext],
) -> None:
    client, ctx = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"), ("p.png", b"prescription"))
    submit(client, claim_id, field_total="20.00")
    claim = ctx.store.load_claim(claim_id)
    assert claim is not None
    assert [(e.field, e.typed_value) for e in claim.edits] == [("total", "2000")]


def test_unreadable_photo_shows_retake_and_category_pick_without_error(
    web: tuple[TestClient, WebContext],
) -> None:  # Review Focus 1
    client, ctx = web
    claim_id, _ = upload(client, ("blank.png", b"blank"))
    page = client.get(f"/claims/{claim_id}/check")
    assert page.status_code == 200
    assert "clearer photo" in page.text and 'name="category"' in page.text
    submit(client, claim_id, field_total="")
    decision = ctx.store.load_decision(claim_id)
    assert decision is not None and decision.lane != "auto_approve"


def test_bad_money_text_shows_a_field_error_and_keeps_other_input(
    web: tuple[TestClient, WebContext],
) -> None:  # Review Focus 4
    client, ctx = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"))
    response = submit(client, claim_id, field_total="12,50x", field_patient_name="Sara A.")
    assert response.status_code == 400  # type: ignore[attr-defined]
    assert "12,50x" in response.text and "Sara A." in response.text  # type: ignore[attr-defined]
    assert "amount like 150.00" in response.text  # type: ignore[attr-defined]
    claim = ctx.store.load_claim(claim_id)
    assert claim is not None and claim.status == "draft"


def test_one_bad_file_is_refused_and_the_others_kept(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web  # Review Focus 5
    response = client.post(
        "/claims",
        data={"consent": "yes", "patient": member_id(0)},
        files=[
            ("photos", ("r.png", b"pharmacy", "image/png")),
            ("photos", ("notes.gif", b"GIF89a", "image/gif")),
        ],
    )
    assert response.status_code == 200 and "notes.gif" in response.text
    drafts = [c for c in ctx.store.list_claims() if c.status == "draft"]
    assert len(drafts) == 1 and len(drafts[0].documents) == 1


def test_adding_the_missing_document_clears_the_request(
    web: tuple[TestClient, WebContext],
) -> None:
    client, ctx = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"))
    client.post(
        f"/claims/{claim_id}/documents",
        files=[("photos", ("p.png", b"prescription", "image/png"))],
    )
    assert len(ctx.store.load_readings(claim_id)) == 2
    submit(client, claim_id)
    decision = ctx.store.load_decision(claim_id)
    assert decision is not None and decision.self_fix_request is None


def test_fix_goes_back_to_the_check_step_and_records_what_was_asked(
    web: tuple[TestClient, WebContext],
) -> None:
    client, ctx = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"), ("p.png", b"prescription"))
    submit(client, claim_id)
    decision = ctx.store.load_decision(claim_id)
    assert decision is not None
    asked = SelfFixRequest(kind="check_photo", field="total", text="t")
    ctx.store.save_decision(
        decision.model_copy(update={"lane": "self_fix", "self_fix_request": asked})
    )
    response = client.post(
        f"/claims/{claim_id}/fix",
        files=[("photos", ("r2.png", b"pharmacy", "image/png"))],
        follow_redirects=False,
    )
    assert response.headers["location"].startswith(f"/claims/{claim_id}/check")
    claim = ctx.store.load_claim(claim_id)
    assert claim is not None
    assert (claim.status, claim.retries_used, claim.retake_fields) == ("draft", 1, ["total"])


def test_review_card_shows_read_and_typed_side_by_side(web: tuple[TestClient, WebContext]) -> None:
    client, ctx = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"), ("p.png", b"prescription"))
    submit(client, claim_id, field_total="20.00")
    decision = ctx.store.load_decision(claim_id)
    assert decision is not None and decision.lane == "human_review"
    card = client.get(f"/review/{claim_id}").text
    assert "17.25" in card and "20.00" in card and "contradicts" in card


def test_patient_mismatch_says_it_is_the_account(web: tuple[TestClient, WebContext]) -> None:
    client, _ = web
    claim_id, _ = upload(client, ("r.png", b"other-patient"))
    page = client.get(f"/claims/{claim_id}/check").text
    assert "your account" in page
