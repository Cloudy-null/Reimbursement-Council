"""The website: member claim flow, reviewer queue and card, and the numbers page.

Routes are thin: they load, call the pipeline, and render. All logic lives in core.
Member claim routes are in claim_routes.py, adding a member in member_routes.py;
what routes share is in context.py.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from reimbursement_council.adapters.storage import ReviewRecord
from reimbursement_council.core.money import parse_sar_to_halalas
from reimbursement_council.web.check_routes import add_check_routes
from reimbursement_council.web.claim_routes import add_claim_routes
from reimbursement_council.web.confirm_routes import add_confirm_routes
from reimbursement_council.web.context import (
    HERE,
    WebContext,
    asset_version,
    claim_view,
    make_page,
)
from reimbursement_council.web.errors import add_error_pages
from reimbursement_council.web.export_routes import add_export_routes
from reimbursement_council.web.i18n import text_for
from reimbursement_council.web.member_routes import add_member_routes
from reimbursement_council.web.numbers import find_reader_scores, find_runs
from reimbursement_council.web.reviewer_check import reviewer_health, reviewer_status_line

__all__ = ["WebContext", "create_app"]


def create_app(ctx: WebContext) -> FastAPI:
    app = FastAPI(title="Reimbursement Council")
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
    page = make_page(
        Jinja2Templates(directory=HERE / "templates"),
        css_version=asset_version(HERE / "static" / "app.css"),
    )
    add_claim_routes(app, ctx, page)
    add_check_routes(app, ctx, page)
    add_export_routes(app, ctx)
    add_confirm_routes(app, ctx)
    add_member_routes(app, ctx, page)
    add_error_pages(app, page)

    @app.get("/review", response_class=HTMLResponse)
    def queue(request: Request, lang: str = "en") -> HTMLResponse:
        waiting = [
            d
            for d in ctx.store.list_decisions(lane="human_review")
            if ctx.store.load_review(d.claim_id) is None
        ]
        return page(request, "queue.html", lang, decisions=waiting)

    @app.get("/review/{claim_id}", response_class=HTMLResponse)
    def review_card(request: Request, claim_id: str, lang: str = "en") -> HTMLResponse:
        return page(
            request,
            "review.html",
            lang,
            opened=datetime.now(UTC).isoformat(),
            **claim_view(ctx, claim_id, lang),
        )

    @app.post("/review/{claim_id}")
    def save_review(
        claim_id: str,
        action: Annotated[str, Form()],
        opened: Annotated[str, Form()],
        reason: Annotated[str, Form()] = "",
        amount: Annotated[str, Form()] = "",
        lang: Annotated[str, Form()] = "en",
    ) -> RedirectResponse:
        if ctx.store.load_decision(claim_id) is None:
            raise HTTPException(status_code=404, detail="No such claim.")
        halalas = parse_sar_to_halalas(amount) if amount else None
        if action == "approve_amount" and halalas is None:
            raise HTTPException(status_code=400, detail="Write the amount like 150.00")
        try:
            started = datetime.fromisoformat(opened)
            record = ReviewRecord(
                claim_id=claim_id,
                reviewer="demo reviewer",
                started_at=started,
                finished_at=datetime.now(UTC),
                action=action,
                amount=halalas,
                reason=reason,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail="Pick an action.") from error
        ctx.store.save_review(record)
        return RedirectResponse(f"/review?lang={lang}", status_code=303)

    @app.get("/metrics", response_class=HTMLResponse)
    def numbers(request: Request, lang: str = "en") -> HTMLResponse:
        runs = find_runs(ctx.results_root)
        readers = find_reader_scores(ctx.results_root)
        line = reviewer_status_line(reviewer_health(ctx), text_for(lang))
        return page(request, "metrics.html", lang, runs=runs, readers=readers, reviewer_line=line)

    return app
