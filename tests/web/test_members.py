"""Adding a member on the website: the form, saving, and the new person in the claim list."""

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from reimbursement_council.web.context import WebContext
from reimbursement_council.web.i18n import text_for
from tests.web.check_helpers import submit

Web = tuple[TestClient, WebContext]


def good_form(**changes: str) -> dict[str, str]:
    values = {
        "lang": "en",
        "name": "Sara Ahmed",
        "name_ar": "سارة أحمد",
        "tier": "silver",
        "dependants": "Omar Ahmed\r\n\r\nLina Ahmed\r\n",
        "used_dental": "600",
        "used_lab": "",
    }
    values.update(changes)
    return values


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_form_renders_in_both_languages(web: Web, lang: str) -> None:
    client, _ = web
    response = client.get(f"/members/new?lang={lang}")
    assert response.status_code == 200
    text = text_for(lang)
    assert text["member_title"] in response.text
    assert text["member_dependants"] in response.text
    assert 'name="used_dental"' in response.text
    assert '<option value="silver"' in response.text


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_new_claim_page_links_to_the_form(web: Web, lang: str) -> None:
    client, _ = web
    page = client.get(f"/?lang={lang}").text
    assert f'href="/members/new?lang={lang}"' in page
    assert text_for(lang)["member_add_link"] in page


def test_post_creates_the_member_and_selects_them(web: Web) -> None:
    client, ctx = web
    before = len(ctx.reference.members)
    response = client.post("/members", data=good_form(), follow_redirects=False)
    assert response.status_code == 303
    location = urlparse(response.headers["location"])
    assert location.path == "/"
    member_id = parse_qs(location.query)["patient"][0]
    (added,) = ctx.store.list_new_members()
    assert added.members[0].member_id == member_id
    assert [m.display_name for m in added.members] == ["Sara Ahmed", "Omar Ahmed", "Lina Ahmed"]
    assert added.histories[0].limits_used == {"dental": 60000}
    assert len(ctx.reference.members) == before + 3
    page = client.get(response.headers["location"]).text
    assert f'<option value="{member_id}" selected>Sara Ahmed</option>' in page
    assert "Lina Ahmed" in page


def test_a_claim_for_the_new_member_is_decided(web: Web) -> None:
    client, ctx = web
    client.post("/members", data=good_form(dependants=""), follow_redirects=False)
    member_id = ctx.store.list_new_members()[0].members[0].member_id
    response = client.post(
        "/claims",
        data={"consent": "yes", "patient": member_id},
        files=[("photos", ("receipt.png", b"pharmacy", "image/png"))],
        follow_redirects=False,
    )
    assert response.status_code == 303
    claim_id = response.headers["location"].split("/claims/")[1].split("/")[0]
    submit(client, claim_id)
    (claim,) = ctx.store.list_claims()
    assert claim.patient_member_id == member_id
    assert ctx.store.load_decision(claim_id) is not None


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"name": ""}, "member_name_missing"),
        ({"name": "Sara 2"}, "member_name_digits"),
        ({"tier": "platinum"}, "member_tier_unknown"),
        ({"used_dental": "-5"}, "member_amount_bad"),
        ({"used_spa": "10"}, "member_benefit_unknown"),
        ({"dependants": "\n".join(f"Child {c}" for c in "abcdef")}, "member_too_many"),
    ],
)
@pytest.mark.parametrize("lang", ["en", "ar"])
def test_bad_post_shows_the_error_and_saves_nothing(
    web: Web, changes: dict[str, str], code: str, lang: str
) -> None:
    client, ctx = web
    before = ctx.reference
    response = client.post("/members", data=good_form(lang=lang, **changes))
    assert response.status_code == 400
    assert text_for(lang)[code] in response.text
    assert text_for(lang)["member_errors"] in response.text
    assert ctx.store.list_new_members() == []
    assert ctx.reference is before


def test_bad_post_keeps_what_was_typed(web: Web) -> None:
    client, _ = web
    response = client.post("/members", data=good_form(name="Sara 2"))
    assert 'value="Sara 2"' in response.text
    assert 'value="600"' in response.text
    assert "Lina Ahmed" in response.text


def test_added_members_are_there_after_a_restart(web: Web) -> None:
    client, ctx = web
    client.post("/members", data=good_form(), follow_redirects=False)
    restarted = WebContext(
        settings=ctx.settings,
        reference=ctx._seed,
        store=ctx.store,
        reader_for=ctx.reader_for,
        uploads=ctx.uploads,
        samples=ctx.samples,
        results_root=ctx.results_root,
    )
    assert restarted.reference == ctx.reference
