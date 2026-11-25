"""One-tap date confirm: when we asked about the treatment date, the member sees the date we
read and answers yes or no instead of taking a new photo.

Yes: core/date_confirm.py decides what the tap may do. When another document shows the same
date, or nothing else shows a date and the claim is far from the claim window limit, the claim
is decided again with the confirmed date. Otherwise a person checks the date (a member's tap
alone never decides a hard rule such as "late"). No goes back to the check step to correct it.
"""

from datetime import date
from typing import Annotated

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import RedirectResponse

from reimbursement_council.core.date_confirm import confirm_verdict
from reimbursement_council.core.models.claim import Claim, FieldEdit
from reimbursement_council.core.models.common import FieldName
from reimbursement_council.core.models.decision import Decision
from reimbursement_council.web.context import WebContext, decide, load_claim, preview

DATE_FIELD: FieldName = "treatment_date"


def read_date(ctx: WebContext, claim: Claim) -> str | None:
    """The treatment date read from the billing document, as the member would see it."""
    documents = preview(ctx, claim)
    if documents.primary_id is None:
        return None
    best = documents.readings[documents.primary_id].best(DATE_FIELD)
    return None if best is None else best.value


def asks_for_the_date(decision: Decision | None) -> bool:
    return (
        decision is not None
        and decision.lane == "self_fix"
        and decision.self_fix_request is not None
        and decision.self_fix_request.field == DATE_FIELD
    )


def confirm_date_for(ctx: WebContext, claim: Claim, decision: Decision | None) -> str | None:
    """The date to show with the yes and no buttons, or None when we did not ask about it."""
    return read_date(ctx, claim) if asks_for_the_date(decision) else None


def date_value(text: str) -> date:
    return date.fromisoformat(text[:10])


def _with_confirmed_date(ctx: WebContext, claim: Claim, read: str) -> Claim:
    """The claim as sent, plus a one-tap confirm of the date we read on the billing document."""
    primary = preview(ctx, claim).primary_id
    assert primary is not None  # read_date found a date on it
    edit = FieldEdit(
        document_id=primary,
        field=DATE_FIELD,
        read_value=read,
        typed_value=read,
        confirmed=True,
    )
    others = [e for e in claim.edits if e.field != DATE_FIELD]
    return claim.model_copy(update={"edits": [*others, edit]})


def add_confirm_routes(app: FastAPI, ctx: WebContext) -> None:
    @app.post("/claims/{claim_id}/confirm-date")
    def confirm_date(
        claim_id: str,
        answer: Annotated[str, Form()],
        lang: Annotated[str, Form()] = "en",
    ) -> RedirectResponse:
        claim = load_claim(ctx, claim_id)
        decision = ctx.store.load_decision(claim_id)
        date = read_date(ctx, claim)
        if claim.status == "draft" or not asks_for_the_date(decision) or date is None:
            raise HTTPException(status_code=409, detail="We did not ask about the date.")
        assert decision is not None  # checked by asks_for_the_date
        if answer == "yes":
            confirmed = _with_confirmed_date(ctx, claim, date)
            judged = [e for e in preview(ctx, confirmed).edits if e.confirmed]
            evidence = judged[0].evidence if judged else "none"
            verdict, why = confirm_verdict(
                evidence,
                date_value(date),
                claim.submitted_at.date(),
                ctx.settings.policy.claim_window_days,
                ctx.settings.decision.confirm_date_margin_days,
            )
            if verdict == "use_date":
                decide(ctx, confirmed)
                return RedirectResponse(f"/claims/{claim_id}?lang={lang}", status_code=303)
            reason = (
                f"The member confirmed the treatment date {date} with one tap; the photo did not "
                f"show it clearly and {why}. A person checks the date."
            )
            update = {
                "lane": "human_review",
                "outcome": "queued",
                "self_fix_request": None,
                "lane_reason": reason,
            }
            ctx.store.save_decision(decision.model_copy(update=update))
            return RedirectResponse(f"/claims/{claim_id}?lang={lang}", status_code=303)
        if answer != "no":
            raise HTTPException(status_code=400, detail="Answer yes or no.")
        if claim.retries_used >= ctx.settings.decision.self_fix_max_retries:
            raise HTTPException(status_code=409, detail="No more tries are left for this claim.")
        asked = list(claim.retake_fields)
        if DATE_FIELD not in asked:
            asked.append(DATE_FIELD)
        draft = claim.model_copy(
            update={
                "status": "draft",
                "retries_used": claim.retries_used + 1,
                "retake_fields": asked,
                "edits": [],
            }
        )
        ctx.store.save_claim(draft)
        return RedirectResponse(f"/claims/{claim_id}/check?lang={lang}", status_code=303)
