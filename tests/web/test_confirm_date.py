"""One-tap date confirm: the member answers yes or no instead of retaking a photo."""

from datetime import timedelta

from fastapi.testclient import TestClient

from reimbursement_council.core.models.decision import SelfFixRequest
from reimbursement_council.web.context import WebContext
from tests.web.check_helpers import TREATED, submit, upload


def asked_about_the_date(web: tuple[TestClient, WebContext]) -> str:
    client, ctx = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"), ("p.png", b"prescription"))
    submit(client, claim_id)
    decision = ctx.store.load_decision(claim_id)
    assert decision is not None
    request = SelfFixRequest(kind="confirm_field", field="treatment_date", text="t")
    ctx.store.save_decision(
        decision.model_copy(update={"lane": "self_fix", "self_fix_request": request})
    )
    return claim_id


def test_the_result_page_shows_the_read_date_with_two_buttons(
    web: tuple[TestClient, WebContext],
) -> None:
    claim_id = asked_about_the_date(web)
    page = web[0].get(f"/claims/{claim_id}").text
    assert TREATED in page and f"/claims/{claim_id}/confirm-date" in page
    assert 'value="yes"' in page and 'value="no"' in page


def test_yes_with_the_same_date_on_another_document_needs_no_person(
    web: tuple[TestClient, WebContext],
) -> None:
    """Core day 4: the prescription shows the same date, so the tap counts and no person is
    needed; the claim is decided again with the confirmed date."""
    client, ctx = web
    claim_id = asked_about_the_date(web)
    response = client.post(
        f"/claims/{claim_id}/confirm-date", data={"answer": "yes"}, follow_redirects=False
    )
    assert response.status_code == 303
    decision = ctx.store.load_decision(claim_id)
    assert decision is not None and decision.lane != "human_review"
    claim = ctx.store.load_claim(claim_id)
    assert claim is not None
    confirmed = [e for e in claim.edits if e.confirmed]
    assert [e.typed_value for e in confirmed] == [TREATED]


def test_yes_near_the_claim_window_limit_goes_to_a_person(
    web: tuple[TestClient, WebContext],
) -> None:
    client, ctx = web
    claim_id = asked_about_the_date(web)
    # Pretend the claim was sent 89 days after the treatment: within 7 days of the 90 day limit.
    claim = ctx.store.load_claim(claim_id)
    assert claim is not None
    late = claim.submitted_at + timedelta(days=87)
    ctx.store.save_claim(claim.model_copy(update={"submitted_at": late}))
    # Take the date off the prescription, so nothing else can confirm it.
    other = [d.document_id for d in claim.documents][1]
    readings = dict(ctx.store.load_readings(claim_id))
    readings[other] = readings[other].model_copy(
        update={"fields": [f for f in readings[other].fields if f.name != "treatment_date"]}
    )
    ctx.store.save_readings(claim_id, readings)
    client.post(f"/claims/{claim_id}/confirm-date", data={"answer": "yes"})
    decision = ctx.store.load_decision(claim_id)
    assert decision is not None and decision.lane == "human_review"
    assert "confirmed" in decision.lane_reason and TREATED in decision.lane_reason
    assert "limit" in decision.lane_reason


def test_no_goes_back_to_the_check_step_without_a_new_photo(
    web: tuple[TestClient, WebContext],
) -> None:
    client, ctx = web
    claim_id = asked_about_the_date(web)
    response = client.post(
        f"/claims/{claim_id}/confirm-date", data={"answer": "no"}, follow_redirects=False
    )
    assert response.headers["location"].startswith(f"/claims/{claim_id}/check")
    claim = ctx.store.load_claim(claim_id)
    assert claim is not None and claim.status == "draft" and claim.retries_used == 1
    assert claim.retake_fields == ["treatment_date"]


def test_confirm_is_refused_when_the_date_was_not_asked(web: tuple[TestClient, WebContext]) -> None:
    client, _ = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"), ("p.png", b"prescription"))
    submit(client, claim_id)
    assert (
        client.post(f"/claims/{claim_id}/confirm-date", data={"answer": "yes"}).status_code == 409
    )
