"""fix/final: a hard rule failed on confident data rejects the claim on every path."""

from fastapi.testclient import TestClient

from reimbursement_council.web.context import WebContext
from tests.web.check_helpers import submit, upload


def test_an_old_claim_without_a_receipt_is_rejected_not_sent_to_a_person(
    web: tuple[TestClient, WebContext],
) -> None:
    """The reviewer card from the owner: no receipt, a document dated 2024-03-06."""
    client, ctx = web
    claim_id, _ = upload(client, ("p.png", b"old-prescription"))
    page = client.get(f"/claims/{claim_id}/check?lang=en").text
    assert 'id="rule-warnings"' in page and "90" in page  # warned before submit
    submit(client, claim_id)
    decision = ctx.store.load_decision(claim_id)
    assert decision is not None and decision.lane == "auto_reject"
    assert "late" in decision.lane_reason


def test_send_to_a_reviewer_cannot_move_a_rejected_claim_to_a_person(
    web: tuple[TestClient, WebContext],
) -> None:
    client, ctx = web
    claim_id, _ = upload(client, ("p.png", b"old-prescription"))
    submit(client, claim_id)
    client.post(f"/claims/{claim_id}/to-reviewer", data={"lang": "en"})
    decision = ctx.store.load_decision(claim_id)
    assert decision is not None and decision.lane == "auto_reject"
