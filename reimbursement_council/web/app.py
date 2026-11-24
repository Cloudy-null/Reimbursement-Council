"""The website: member claim flow, reviewer queue and card, and the numbers page.

Routes are thin: they load, call the pipeline, and render. All logic lives in core.
Member claim routes are in claim_routes.py; what routes share is in context.py.
"""

import json
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
from reimbursement_council.web.export_routes import add_export_routes

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
        runs = []
        for path in sorted(ctx.results_root.glob("**/results*.json")):
            report = json.loads(path.read_text(encoding="utf-8"))
            runs.append({"name": f"{path.parent.name} / {path.stem}", "report": report})
        readers = []
        for path in sorted(ctx.results_root.glob("**/accuracy.json")):
            report = json.loads(path.read_text(encoding="utf-8"))
            readers.append(
                {"name": path.parent.name, "summary": report["summary"], "reader": report["reader"]}
            )
        return page(request, "metrics.html", lang, runs=runs, readers=readers)

    return app
