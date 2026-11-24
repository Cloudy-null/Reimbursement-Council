"""What every website route shares: the context, page rendering, deciding a claim, and the
claim view used by the member result page and the reviewer card."""

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
from reimbursement_council.core.extraction import extract_document
from reimbursement_council.core.models.claim import Claim, Document, ExtractionResult
from reimbursement_council.core.models.reference import ReferenceData
from reimbursement_council.core.payout import calculate_payout
from reimbursement_council.pipeline.process_claim import process_claim
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
        context = {"t": text_for(lang), "lang": "ar" if lang == "ar" else "en", **values}
        return templates.TemplateResponse(request, name, context)

    return page


def decide(ctx: WebContext, claim: Claim) -> None:
    process_claim(
        claim,
        ctx.reference,
        ctx.settings,
        ctx.store,
        datetime.now(UTC),
        reader_for=ctx.reader_for,
    )
    ctx.store.save_claim(claim)


def _read(ctx: WebContext, claim: Claim) -> ExtractionResult | None:
    document = claim.documents[0] if claim.documents else None
    if document is None:
        return None
    reading = ctx.reader_for(document).read(document)
    return extract_document(document.document_id, reading, ctx.settings)


def claim_view(ctx: WebContext, claim_id: str) -> dict[str, Any]:
    claim = ctx.store.load_claim(claim_id)
    decision = ctx.store.load_decision(claim_id)
    if claim is None or decision is None:
        raise HTTPException(status_code=404, detail="No such claim.")
    extraction = _read(ctx, claim)
    payout = None
    if extraction is not None:
        policy = ctx.reference.policy(claim.policy_id)
        history = ctx.reference.history(claim.patient_member_id)
        payout = calculate_payout(extraction, policy, history, ctx.settings)
    floor = ctx.settings.decision.hard_rule_confidence_floor
    return {
        "claim": claim,
        "decision": decision,
        "fields": field_rows(extraction, floor, ctx.settings.policy.local_utc_offset_hours),
        "items": [] if extraction is None else extraction.line_items,
        "money": payout_lines(payout, [] if extraction is None else extraction.line_items),
        "review": ctx.store.load_review(claim_id),
    }
