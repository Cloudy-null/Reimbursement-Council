"""Final website pass: check page order and choices, reviewer queue bands, reviewer card."""

from fastapi.testclient import TestClient

from reimbursement_council.core.models.decision import Decision
from reimbursement_council.web.context import WebContext
from reimbursement_council.web.review_view import band, field_rows, riskiest_first, why_reasons
from tests.factories import repo_settings
from tests.web.check_helpers import submit, upload


def test_the_read_values_come_first_and_a_missing_document_offers_two_choices(
    web: tuple[TestClient, WebContext],
) -> None:
    client, _ = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"))  # no prescription: one is missing
    for lang, add, send in (
        ("en", "Add it now", "Send without it"),
        ("ar", "أضفه الآن", "أرسل بدونه"),
    ):
        page = client.get(f"/claims/{claim_id}/check?lang={lang}").text
        assert page.index('id="read-fields"') < page.index('id="missing"') < page.index("doc-grid")
        assert add in page and send in page
        assert 'class="choice primary-choice' in page


def test_bands_follow_config_and_the_riskiest_comes_first() -> None:
    settings = repo_settings()
    assert band(0.95, settings) == "likely_ok"
    assert band(0.6, settings) == "unsure"
    assert band(0.1, settings) == "likely_not"


def test_why_lists_only_what_sent_it_to_a_person() -> None:
    export = {
        "decision": {"rule_results": [
            {"rule": "late", "outcome": "pass", "reason": "on time"},
            {"rule": "member_edit", "outcome": "not_sure", "reason": "typed total differs"},
        ]},
        "invoice": {"checks": [
            {"name": "qr_matches_text", "passed": False, "reason": "QR total differs"},
        ]},
        "cross_checks": [{"name": "dates_agree", "passed": True, "details": "dates agree"}],
        "missing_documents": [["prescription"]],
    }  # fmt: skip
    reasons = why_reasons(export, "lane reason")
    assert reasons == ["typed total differs", "QR total differs", "Missing: prescription"]


def test_a_field_the_member_typed_is_marked_with_the_value_we_read() -> None:
    export = {
        "documents": [{"document_id": "d", "kind": "receipt", "fields": [
            {"name": "total", "value": "51000", "source": "member_typed"},
            {"name": "treatment_date", "value": "2026-11-20", "source": "ocr"},
        ]}],
        "member_edits": [{"document_id": "d", "field": "total", "read_value": "46000"}],
    }  # fmt: skip
    rows = {r["name"]: r for r in field_rows(export)}
    assert rows["total"]["typed"] and rows["total"]["read_value"] == "46000"
    assert not rows["treatment_date"]["typed"]


def test_the_queue_shows_a_band_label_and_the_card_shows_why_first(
    web: tuple[TestClient, WebContext],
) -> None:
    client, ctx = web
    claim_id, _ = upload(client, ("r.png", b"pharmacy"), ("p.png", b"prescription"))
    submit(client, claim_id, field_total="999.00")  # a typed total the QR contradicts: a person
    decision = ctx.store.load_decision(claim_id)
    assert decision is not None and decision.lane == "human_review"
    queue = client.get("/review?lang=en").text
    assert "band-" in queue and any(x in queue for x in ("Likely OK", "Unsure", "Likely not"))
    card = client.get(f"/review/{claim_id}?lang=en").text
    assert card.index('id="why"') < card.index('id="claim-data"')
    assert "Typed by member" in card and 'id="all-checks"' in card and "View documents" in card
    ordered = riskiest_first([decision, decision.model_copy(update={"p_good": 0.01})])
    assert [d.p_good for d in ordered][0] == 0.01
    assert isinstance(ordered[0], Decision)
