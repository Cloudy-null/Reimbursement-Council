"""The check step (spec 6.5): show each document with its type and what was read, the missing
documents and the mismatches; take the member's corrections; then submit to the pipeline.

Also: add documents to a draft, and go back to the check step from a self-fix request.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from reimbursement_council.adapters.readers import PDF_SUFFIX
from reimbursement_council.adapters.readers import document_image as document_image_bytes
from reimbursement_council.config.message_models import LanguageMessages
from reimbursement_council.core.decision.document_requests import (
    document_label,
    mismatch_documents,
)
from reimbursement_council.core.models.claim import Claim, ExtractionResult
from reimbursement_council.core.models.common import FieldName
from reimbursement_council.core.payout import calculate_payout
from reimbursement_council.core.payout_preview import estimate_lines
from reimbursement_council.pipeline.document_set import DocumentSet
from reimbursement_council.web.check_form import (
    DOCUMENT_KINDS,
    EDITABLE,
    chosen_categories,
    chosen_kinds,
    form_value,
    parse_edits,
)
from reimbursement_council.web.context import (
    Page,
    WebContext,
    claim_view,
    decide,
    load_claim,
    preview,
)
from reimbursement_council.web.uploads import accept, collect, read_and_store, store_documents

ASKED_KINDS = frozenset({"retake_photo", "check_photo", "fix_mismatch"})
"""Requests about one field: asked once, then a human (claim.retake_fields)."""


def _estimate(
    ctx: WebContext, claim: Claim, reading: ExtractionResult | None, language: LanguageMessages
) -> list[str]:
    """The payout we expect and why it is lower, shown before the member sends the claim."""
    if reading is None:
        return []
    try:
        policy = ctx.reference.policy(claim.policy_id)
        history = ctx.reference.history(claim.patient_member_id)
    except LookupError:
        return []
    tier = ctx.settings.policy.tiers.get(policy.tier)
    if tier is None:
        return []
    payout = calculate_payout(reading, policy, history, ctx.settings)
    vat = reading.money("vat_total") or 0
    return estimate_lines(payout, tier, history, vat, language)


def check_values(
    ctx: WebContext, claim: Claim, lang: str, form: dict[str, str] | None = None
) -> dict[str, Any]:
    documents: DocumentSet = preview(ctx, claim)
    language = ctx.settings.messages.ar if lang == "ar" else ctx.settings.messages.en
    primary = documents.primary_id
    reading = None if primary is None else documents.readings[primary]
    read = _read_values(reading)
    values = {f: form_value(f, read[f]) for f in EDITABLE}
    selected_kinds: dict[str, str] = {d.document_id: d.kind for d in documents.documents}
    selected_category = claim.claim_categories[0] if claim.claim_categories else ""
    if form is not None:  # a re-render after an error keeps everything the member chose
        values |= {f: form.get(f"field_{f}", "") for f in EDITABLE}
        selected_kinds |= {
            d: form[f"kind_{d}"]
            for d in selected_kinds
            if form.get(f"kind_{d}", "") in DOCUMENT_KINDS
        }
        selected_category = form.get("category", "")
    mismatches = []
    for check in documents.cross_checks:
        if check.passed is False:
            kinds = {d.document_id: d.kind for d in documents.documents}
            names = mismatch_documents(check, kinds)
            label = language.fields.get(check.field, check.field)
            text = " / ".join(document_label(language, name) for name in names)
            mismatches.append(language.requests.mismatch.format(field=label, documents=text))
    unread = [d.document_id for d in documents.documents if d.kind == "other"]
    return {
        "claim": claim,
        "documents": documents.documents,
        "primary_id": primary,
        "kinds": DOCUMENT_KINDS,
        "selected_kinds": selected_kinds,
        "selected_category": selected_category,
        "kind_names": {k: document_label(language, k) for k in DOCUMENT_KINDS},
        "missing": [
            need.request.ar if lang == "ar" else need.request.en for need in documents.missing
        ]
        + [
            language.requests.add_document.format(field=language.fields.get(r.field, r.field))
            for r in documents.rule_requests
        ],
        "estimate": _estimate(ctx, claim, reading, language),
        "mismatches": mismatches,
        "unread": unread,
        "categories": list(ctx.settings.documents.required_by_category),
        "chosen_categories": documents.categories,
        "editable": EDITABLE if primary is not None else (),
        "values": values,
        "low": {
            f
            for f in EDITABLE
            if reading is not None
            and (b := reading.best(f)) is not None
            and b.confidence < ctx.settings.decision.hard_rule_confidence_floor
        },
    }


def _read_values(reading: ExtractionResult | None) -> dict[FieldName, str | None]:
    values: dict[FieldName, str | None] = {}
    for field in EDITABLE:
        best = None if reading is None else reading.best(field)
        values[field] = None if best is None else best.value
    return values


def add_check_routes(app: FastAPI, ctx: WebContext, page: Page) -> None:
    @app.get("/claims/{claim_id}/check", response_class=HTMLResponse)
    def check(request: Request, claim_id: str, lang: str = "en") -> HTMLResponse:
        claim = load_claim(ctx, claim_id)
        if claim.status != "draft":
            raise HTTPException(status_code=409, detail="This claim was already sent.")
        return page(request, "check_claim.html", lang, **check_values(ctx, claim, lang))

    @app.post("/claims/{claim_id}/documents", response_model=None)
    async def add_documents(
        request: Request,
        claim_id: str,
        photos: Annotated[list[UploadFile] | None, File()] = None,
        lang: Annotated[str, Form()] = "en",
    ) -> Response:
        claim = load_claim(ctx, claim_id)
        if claim.status != "draft":
            raise HTTPException(status_code=409, detail="This claim was already sent.")
        kept, refused = accept(
            await collect(photos),
            ctx.settings.documents.max_upload_megabytes,
            ctx.settings.documents.max_files_per_upload,
        )
        added = store_documents(ctx, claim_id, kept, datetime.now(UTC))
        await run_in_threadpool(read_and_store, ctx, claim_id, added)  # OCR: off the loop
        claim = claim.model_copy(update={"documents": [*claim.documents, *added]})
        ctx.store.save_claim(claim)
        if refused:
            values = check_values(ctx, claim, lang) | {"refused": refused, "status_code": 400}
            return page(request, "check_claim.html", lang, **values)
        return RedirectResponse(f"/claims/{claim_id}/check?lang={lang}", status_code=303)

    @app.post("/claims/{claim_id}/submit", response_model=None)
    async def submit(request: Request, claim_id: str) -> Response:
        claim = load_claim(ctx, claim_id)
        if claim.status != "draft":
            raise HTTPException(status_code=409, detail="This claim was already sent.")
        form = {k: v for k, v in (await request.form()).items() if isinstance(v, str)}
        lang = form.get("lang", "en")
        documents = preview(ctx, claim)
        primary = documents.primary_id
        reading = None if primary is None else documents.readings[primary]
        read = _read_values(reading)
        edits, errors = parse_edits(form, primary, read) if primary else ([], {})
        if errors:
            values = check_values(ctx, claim, lang, form) | {"errors": errors, "status_code": 400}
            return page(request, "check_claim.html", lang, **values)
        kinded = chosen_kinds(documents.documents, form)
        categories = chosen_categories(
            form.get("category", ""),
            list(ctx.settings.documents.required_by_category),
            documents.detected_categories,
        )
        sent = claim.model_copy(
            update={
                "documents": kinded,
                "edits": edits,
                "claim_categories": categories,
                "status": "submitted",
                "submitted_at": datetime.now(UTC),
            }
        )
        await run_in_threadpool(decide, ctx, sent)
        return RedirectResponse(f"/claims/{claim_id}?lang={lang}", status_code=303)

    @app.post("/claims/{claim_id}/fix", response_model=None)
    async def fix(
        request: Request,
        claim_id: str,
        photos: Annotated[list[UploadFile] | None, File()] = None,
        replace: Annotated[str, Form()] = "",
        lang: Annotated[str, Form()] = "en",
    ) -> Response:
        """Add or replace a document after a self-fix request, then check again. Only a sent
        claim that waits for a self-fix, with retries left, can go back to the check step."""
        claim = load_claim(ctx, claim_id)
        decision = ctx.store.load_decision(claim_id)
        if (
            claim.status == "draft"
            or decision is None
            or decision.lane != "self_fix"
            or decision.self_fix_request is None
            or claim.retries_used >= ctx.settings.decision.self_fix_max_retries
        ):
            raise HTTPException(status_code=409, detail="This claim is not waiting for a fix.")
        kept, refused = accept(
            await collect(photos),
            ctx.settings.documents.max_upload_megabytes,
            ctx.settings.documents.max_files_per_upload,
        )
        if refused or not kept:  # change nothing, so a bad file never removes a good one
            values = claim_view(ctx, claim_id, lang) | {"refused": refused, "status_code": 400}
            return page(request, "claim.html", lang, **values)
        asked = list(claim.retake_fields)
        asked_request = decision.self_fix_request
        if asked_request.kind in ASKED_KINDS and asked_request.field not in asked:
            asked.append(asked_request.field)
        added = store_documents(ctx, claim_id, kept, datetime.now(UTC))
        await run_in_threadpool(read_and_store, ctx, claim_id, added)  # OCR: off the loop
        documents = [d for d in claim.documents if d.document_id != replace]
        draft = claim.model_copy(
            update={
                "documents": [*documents, *added],
                "retries_used": claim.retries_used + 1,
                "retake_fields": asked,
                "status": "draft",
                "edits": [],
            }
        )
        ctx.store.save_claim(draft)
        return RedirectResponse(f"/claims/{claim_id}/check?lang={lang}", status_code=303)

    @app.get("/claims/{claim_id}/documents/{document_id}")
    def document_image(claim_id: str, document_id: str) -> Response:
        """The document's file; a PDF is shown as the image the reader reads."""
        claim = load_claim(ctx, claim_id)
        for document in claim.documents:
            if document.document_id == document_id:
                if Path(document.file_path).suffix.lower() == PDF_SUFFIX:
                    image = document_image_bytes(document, ctx.settings)
                    return Response(image, media_type="image/png")
                return FileResponse(document.file_path)
        raise HTTPException(status_code=404, detail="No such document.")
