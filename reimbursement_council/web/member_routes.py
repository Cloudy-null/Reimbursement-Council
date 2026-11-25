"""Add a member by hand (GET /members/new, POST /members), so a real person can be tested.

Routes are thin: the checks and the building are in core/new_member.py.
"""

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.datastructures import FormData

from reimbursement_council.core.dates import local_date_of
from reimbursement_council.core.new_member import (
    NewMemberError,
    NewMemberForm,
    benefit_keys,
    build_new_member,
)
from reimbursement_council.web.context import Page, WebContext
from reimbursement_council.web.i18n import text_for

USED_PREFIX = "used_"


def _text(data: FormData, name: str) -> str:
    value = data.get(name, "")
    return value if isinstance(value, str) else ""


def _form_from(data: FormData) -> NewMemberForm:
    """Every used_* field is kept, so a benefit the policy does not have is refused, not lost."""
    return NewMemberForm(
        name=_text(data, "name"),
        name_ar=_text(data, "name_ar"),
        tier=_text(data, "tier"),
        dependants=tuple(_text(data, "dependants").splitlines()),
        used={
            name.removeprefix(USED_PREFIX): value
            for name, value in data.items()
            if name.startswith(USED_PREFIX) and isinstance(value, str)
        },
    )


def _values(ctx: WebContext, form: NewMemberForm, lang: str) -> dict[str, Any]:
    text = text_for(lang)
    known = benefit_keys(ctx.settings.policy)
    benefits = [
        {
            "field": f"{USED_PREFIX}{key}",
            "label": text.get(f"cat_{key}", key.replace("_", " ")),
            "value": form.used.get(key, ""),
        }
        for key in known
    ]
    unknown = [f"{USED_PREFIX}{key}" for key in form.used if key not in known]
    return {
        "form": form,
        "tiers": list(ctx.settings.policy.tiers),
        "benefits": benefits,
        "unknown_benefits": unknown,
    }


def add_member_routes(app: FastAPI, ctx: WebContext, page: Page) -> None:
    @app.get("/members/new", response_class=HTMLResponse)
    def new_member(request: Request, lang: str = "en") -> HTMLResponse:
        form = NewMemberForm(name="", tier=next(iter(ctx.settings.policy.tiers), ""))
        return page(request, "new_member.html", lang, errors={}, **_values(ctx, form, lang))

    @app.post("/members", response_model=None)
    async def create_member(request: Request) -> Response:
        data = await request.form()
        lang = "ar" if _text(data, "lang") == "ar" else "en"
        form = _form_from(data)
        now = datetime.now(UTC)
        today = local_date_of(now, ctx.settings.policy.local_utc_offset_hours)
        try:
            added = build_new_member(form, ctx.settings.policy, today, lambda: str(uuid4()))
        except NewMemberError as error:
            return page(
                request,
                "new_member.html",
                lang,
                errors=error.errors,
                status_code=400,
                **_values(ctx, form, lang),
            )
        await run_in_threadpool(ctx.add_member, added, now)
        query = urlencode({"lang": lang, "patient": added.members[0].member_id})
        return RedirectResponse(f"/?{query}", status_code=303)
