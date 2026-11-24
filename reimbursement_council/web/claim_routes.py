"""Member claim routes: new claim (upload step), result, to a reviewer, samples, the image.

Routes are thin: they load, call the pipeline, and render. All logic lives in core.
"""

import random
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from reimbursement_council.adapters.receipt_drawing import DAMAGE_PRESETS, draw_receipt
from reimbursement_council.core.models.claim import Claim
from reimbursement_council.synthetic.receipt_content import (
    PATIENTS,
    PROVIDERS,
    ReceiptOptions,
    make_receipt_content,
)
from reimbursement_council.web.check_routes import check_values
from reimbursement_council.web.confirm_routes import confirm_date_for
from reimbursement_council.web.context import Page, WebContext, claim_view
from reimbursement_council.web.i18n import text_for
from reimbursement_council.web.uploads import accept, collect, read_and_store, store_documents

DEMO_PATIENT = PATIENTS[0]  # the first person in the list, so samples match the default pick
SAMPLES: dict[str, ReceiptOptions] = {
    "clinic": ReceiptOptions(provider=PROVIDERS[0], item_count=1, patient=DEMO_PATIENT),
    "pharmacy": ReceiptOptions(provider=PROVIDERS[2], item_count=2, patient=DEMO_PATIENT),
    "overpriced": ReceiptOptions(
        provider=PROVIDERS[1], item_count=1, price_factor=2.2, patient=DEMO_PATIENT
    ),
    "no_qr": ReceiptOptions(
        provider=PROVIDERS[0], with_qr=False, item_count=2, patient=DEMO_PATIENT
    ),
    "unlisted": ReceiptOptions(
        provider=PROVIDERS[1], item_count=1, unlisted_item=True, patient=DEMO_PATIENT
    ),
}


def ensure_samples(ctx: WebContext) -> list[str]:
    """Draw the sample receipts once, dated a few days ago so they are inside the claim window."""
    ctx.samples.mkdir(parents=True, exist_ok=True)
    issued = (datetime.now(UTC) + timedelta(hours=3) - timedelta(days=3)).replace(tzinfo=None)
    for index, (name, options) in enumerate(SAMPLES.items()):
        path = ctx.samples / f"{name}.png"
        if not path.is_file():
            content = make_receipt_content(
                random.Random(500 + index),
                ctx.settings.prices,
                options.model_copy(update={"issued_at": issued.replace(second=0, microsecond=0)}),
                ctx.settings.policy.vat_rate,
            )
            damage = DAMAGE_PRESETS["none"]
            path.write_bytes(draw_receipt(content, damage).png)
    return list(SAMPLES)


def add_claim_routes(app: FastAPI, ctx: WebContext, page: Page) -> None:
    @app.get("/", response_class=HTMLResponse)
    def new_claim(request: Request, lang: str = "en") -> HTMLResponse:
        return page(
            request,
            "new_claim.html",
            lang,
            people=ctx.reference.members,
            samples=ensure_samples(ctx),
        )

    @app.post("/claims", response_model=None)
    async def create_claim(
        request: Request,
        patient: Annotated[str, Form()],
        lang: Annotated[str, Form()] = "en",
        sample: Annotated[str, Form()] = "",
        photos: Annotated[list[UploadFile] | None, File()] = None,
        consent: Annotated[str, Form()] = "",
    ) -> Response:
        """Step 1 (spec 6.5): save the files as a draft claim. Nothing is decided yet. Nothing
        is read before the member agrees (consent step); the time they agreed is kept."""
        if consent != "yes":
            raise HTTPException(status_code=400, detail=text_for(lang)["consent_needed"])
        try:
            person = ctx.reference.member(patient)
        except LookupError as error:
            raise HTTPException(status_code=400, detail="Pick a person from the list.") from error
        if sample:
            if sample not in SAMPLES:
                raise HTTPException(status_code=400, detail="Unknown sample.")
            ensure_samples(ctx)
            files = [(f"{sample}.png", (ctx.samples / f"{sample}.png").read_bytes())]
        else:
            files = await collect(photos)
        kept, refused = accept(files, ctx.settings.documents.max_upload_megabytes)
        if not kept:
            text = text_for(lang)
            detail = "; ".join(f"{r.name}: {text[r.reason]}" for r in refused)
            detail = detail or "Add a photo or pick a sample receipt."
            raise HTTPException(status_code=400, detail=detail)
        claim_id = str(uuid4())
        now = datetime.now(UTC)
        documents = store_documents(ctx, claim_id, kept, now)
        read_and_store(ctx, claim_id, documents)
        policy = ctx.reference.policy(person.policy_id)
        claimant = patient if patient in policy.covered_people else policy.covered_people[0]
        claim = Claim(
            claim_id=claim_id,
            member_id=claimant,
            patient_member_id=patient,
            policy_id=person.policy_id,
            submitted_at=now,
            status="draft",
            documents=documents,
            retries_used=0,
            consented_at=now,
        )
        ctx.store.save_claim(claim)
        if refused:
            return page(
                request,
                "check_claim.html",
                lang,
                **(check_values(ctx, claim, lang) | {"refused": refused}),
            )
        return RedirectResponse(f"/claims/{claim_id}/check?lang={lang}", status_code=303)

    @app.get("/claims/{claim_id}", response_class=HTMLResponse)
    def show_claim(request: Request, claim_id: str, lang: str = "en") -> HTMLResponse:
        values = claim_view(ctx, claim_id, lang)
        values["confirm_date"] = confirm_date_for(ctx, values["claim"], values["decision"])
        return page(request, "claim.html", lang, **values)

    @app.post("/claims/{claim_id}/to-reviewer")
    def to_reviewer(claim_id: str, lang: Annotated[str, Form()] = "en") -> RedirectResponse:
        decision = ctx.store.load_decision(claim_id)
        if decision is None:
            raise HTTPException(status_code=404, detail="No such claim.")
        ctx.store.save_decision(
            decision.model_copy(
                update={
                    "lane": "human_review",
                    "outcome": "queued",
                    "self_fix_request": None,
                    "lane_reason": "The member chose a reviewer instead of fixing it.",
                }
            )
        )
        return RedirectResponse(f"/claims/{claim_id}?lang={lang}", status_code=303)

    @app.get("/samples/{name}.png")
    def sample_image(name: str) -> FileResponse:
        if name not in SAMPLES:
            raise HTTPException(status_code=404, detail="No such sample.")
        ensure_samples(ctx)
        return FileResponse(ctx.samples / f"{name}.png")

    @app.get("/claims/{claim_id}/document")
    def document(claim_id: str) -> FileResponse:
        claim = ctx.store.load_claim(claim_id)
        if claim is None or not claim.documents:
            raise HTTPException(status_code=404, detail="No such document.")
        return FileResponse(claim.documents[0].file_path)
