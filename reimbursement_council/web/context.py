"""What every website route shares: the context, page rendering, the document set preview,
deciding a claim, and the claim view used by the member result page and the reviewer card."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from reimbursement_council.adapters.readers import DocumentReader
from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import Claim, Document
from reimbursement_council.core.models.reference import Member, ReferenceData
from reimbursement_council.core.payout import calculate_payout
from reimbursement_council.pipeline.document_set import DocumentSet, read_document_set
from reimbursement_council.pipeline.process_claim import process_claim
from reimbursement_council.web.check_form import form_value
from reimbursement_council.web.i18n import text_for
from reimbursement_council.web.views import field_rows, payout_lines

HERE = Path(__file__).resolve().parent

Page = Callable[..., HTMLResponse]
"""page(request, template_name, lang, **values) -> HTMLResponse"""


@dataclass
class WebContext:
    settings: Settings
    reference: ReferenceData
    store: ClaimStore
    reader_for: Callable[[Document], DocumentReader]
    uploads: Path
    samples: Path
    results_root: Path


def make_page(templates: Jinja2Templates) -> Page:
    def page(request: Request, name: str, lang: str, **values: Any) -> HTMLResponse:
        status = values.pop("status_code", 200)
        context = {
            "t": text_for(lang),
            "lang": "ar" if lang == "ar" else "en",
            "sar_text": form_value,
            **values,
        }
        return templates.TemplateResponse(request, name, context, status_code=status)

    return page


def _patient(ctx: WebContext, claim: Claim) -> Member:
    try:
        return ctx.reference.member(claim.patient_member_id)
    except LookupError:
        return ctx.reference.member(claim.member_id)


def preview(ctx: WebContext, claim: Claim) -> DocumentSet:
    """The document set as the pipeline will see it: types, readings, needs, cross checks."""
    readings = ctx.store.load_readings(claim.claim_id)
    return read_document_set(claim, _patient(ctx, claim), ctx.settings, ctx.reader_for, readings)


def load_claim(ctx: WebContext, claim_id: str) -> Claim:
    claim = ctx.store.load_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="No such claim.")
    return claim


def decide(ctx: WebContext, claim: Claim) -> None:
    process_claim(
        claim,
        ctx.reference,
        ctx.settings,
        ctx.store,
        datetime.now(UTC),
        reader_for=ctx.reader_for,
        readings=ctx.store.load_readings(claim.claim_id),
    )
    ctx.store.save_claim(claim)


def claim_view(ctx: WebContext, claim_id: str) -> dict[str, Any]:
    claim = load_claim(ctx, claim_id)
    decision = ctx.store.load_decision(claim_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="No such claim.")
    documents = preview(ctx, claim)
    primary = documents.primary_id
    extraction = None if primary is None else documents.readings[primary]
    payout = None
    if extraction is not None:
        policy = ctx.reference.policy(claim.policy_id)
        history = ctx.reference.history(claim.patient_member_id)
        payout = calculate_payout(extraction, policy, history, ctx.settings)
    floor = ctx.settings.decision.hard_rule_confidence_floor
    items = [] if extraction is None else extraction.line_items
    return {
        "claim": claim,
        "decision": decision,
        "documents": documents.documents,
        "primary_id": primary,
        "edits": documents.edits,
        "fields": field_rows(extraction, floor, ctx.settings.policy.local_utc_offset_hours),
        "items": items,
        "money": payout_lines(payout, items),
        "review": ctx.store.load_review(claim_id),
    }
