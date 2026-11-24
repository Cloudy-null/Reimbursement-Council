"""Member claim routes: new claim, upload, result, self-fix, sample receipts, the document.

Routes are thin: they load, call the pipeline, and render. All logic lives in core.
"""

import hashlib
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from reimbursement_council.adapters.receipt_drawing import DAMAGE_PRESETS, draw_receipt
from reimbursement_council.core.models.claim import Claim, Document
from reimbursement_council.synthetic.receipt_content import (
    PROVIDERS,
    ReceiptOptions,
    make_receipt_content,
)
from reimbursement_council.web.context import Page, WebContext, claim_view, decide

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # a phone photo is a few MB; this only stops abuse

SAMPLES: dict[str, ReceiptOptions] = {
    "clinic": ReceiptOptions(provider=PROVIDERS[0], item_count=1),
    "pharmacy": ReceiptOptions(provider=PROVIDERS[2], item_count=2),
    "overpriced": ReceiptOptions(provider=PROVIDERS[1], item_count=1, price_factor=2.2),
    "no_qr": ReceiptOptions(provider=PROVIDERS[0], with_qr=False, item_count=2),
    "unlisted": ReceiptOptions(provider=PROVIDERS[1], item_count=1, unlisted_item=True),
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


def _store_image(ctx: WebContext, claim_id: str, attempt: int, data: bytes, suffix: str) -> Path:
    if suffix not in IMAGE_SUFFIXES:
        raise HTTPException(status_code=400, detail="Please send a PNG or JPG photo.")
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="The photo is empty or too large.")
    ctx.uploads.mkdir(parents=True, exist_ok=True)
    path = ctx.uploads / f"{claim_id}-{attempt}{suffix}"
    path.write_bytes(data)
    return path


def _document(claim_id: str, path: Path, data: bytes, now: datetime) -> Document:
    return Document(
        document_id=str(uuid4()),
        claim_id=claim_id,
        kind="receipt",
        file_path=str(path),
        image_hash=hashlib.sha256(data).hexdigest(),
        uploaded_at=now,
    )


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

    @app.post("/claims")
    async def create_claim(
        patient: Annotated[str, Form()],
        lang: Annotated[str, Form()] = "en",
        sample: Annotated[str, Form()] = "",
        photo: Annotated[UploadFile | None, File()] = None,
    ) -> RedirectResponse:
        try:
            person = ctx.reference.member(patient)
        except LookupError as error:
            raise HTTPException(status_code=400, detail="Pick a person from the list.") from error
        if sample:
            if sample not in SAMPLES:
                raise HTTPException(status_code=400, detail="Unknown sample.")
            ensure_samples(ctx)
            data, suffix = (ctx.samples / f"{sample}.png").read_bytes(), ".png"
        elif photo is not None and photo.filename:
            data, suffix = await photo.read(), Path(photo.filename).suffix.lower()
        else:
            raise HTTPException(status_code=400, detail="Add a photo or pick a sample receipt.")
        claim_id = str(uuid4())
        now = datetime.now(UTC)
        path = _store_image(ctx, claim_id, 0, data, suffix)
        policy = ctx.reference.policy(person.policy_id)
        claimant = patient if patient in policy.covered_people else policy.covered_people[0]
        claim = Claim(
            claim_id=claim_id,
            member_id=claimant,
            patient_member_id=patient,
            policy_id=person.policy_id,
            submitted_at=now,
            status="submitted",
            documents=[_document(claim_id, path, data, now)],
            retries_used=0,
        )
        decide(ctx, claim)
        return RedirectResponse(f"/claims/{claim_id}?lang={lang}", status_code=303)

    @app.get("/claims/{claim_id}", response_class=HTMLResponse)
    def show_claim(request: Request, claim_id: str, lang: str = "en") -> HTMLResponse:
        return page(request, "claim.html", lang, **claim_view(ctx, claim_id))

    @app.post("/claims/{claim_id}/fix")
    async def fix_claim(
        claim_id: str,
        photo: Annotated[UploadFile, File()],
        lang: Annotated[str, Form()] = "en",
    ) -> RedirectResponse:
        claim = ctx.store.load_claim(claim_id)
        if claim is None:
            raise HTTPException(status_code=404, detail="No such claim.")
        data = await photo.read()
        attempt = claim.retries_used + 1
        path = _store_image(ctx, claim_id, attempt, data, Path(photo.filename or "").suffix.lower())
        now = datetime.now(UTC)
        fixed = claim.model_copy(
            update={
                "documents": [_document(claim_id, path, data, now)],
                "retries_used": attempt,
                "submitted_at": now,
            }
        )
        decide(ctx, fixed)
        return RedirectResponse(f"/claims/{claim_id}?lang={lang}", status_code=303)

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
