"""What the reviewer screens show: the approval band of a claim, the reasons a person is
needed, and the claim data as a field list built from the export. Presentation only."""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.decision import Decision
from reimbursement_council.pipeline.export_claim import export_claim
from reimbursement_council.web.context import WebContext, load_claim

BANDS = ("likely_not", "unsure", "likely_ok")


def export_data(ctx: WebContext, claim_id: str) -> dict[str, Any]:
    """The claim as the export JSON (empty when it was not sent), for the reviewer card."""
    export = export_claim(
        load_claim(ctx, claim_id), ctx.store, ctx.reference, ctx.settings, datetime.now(UTC)
    )
    return {} if export is None else json.loads(export.model_dump_json())


def review_values(ctx: WebContext, claim_id: str, lane_reason: str) -> dict[str, Any]:
    data = export_data(ctx, claim_id)
    return {
        "why_reasons": why_reasons(data, lane_reason),
        "passed_items": passed_items(data),
        "field_rows": field_rows(data),
    }


def band(p_good: float, settings: Settings) -> str:
    """likely_ok, unsure or likely_not, from the band limits in config/decision.yaml."""
    limits = settings.decision.review_bands
    if p_good >= limits.likely_ok:
        return "likely_ok"
    if p_good >= limits.unsure:
        return "unsure"
    return "likely_not"


def riskiest_first(decisions: Sequence[Decision]) -> list[Decision]:
    return sorted(decisions, key=lambda d: d.p_good)


def why_reasons(export: dict[str, Any], lane_reason: str) -> list[str]:
    """Only what sent the claim to a person: rules not passed, checks failed, documents that
    disagree, missing documents and edits the evidence does not back."""
    reasons: list[str] = []
    decision = export.get("decision") or {}
    for rule in decision.get("rule_results") or []:
        if rule.get("outcome") != "pass":
            reasons.append(rule.get("reason") or str(rule.get("rule")))
    for check in (export.get("invoice") or {}).get("checks") or []:
        if check.get("passed") is False:
            reasons.append(check.get("reason") or str(check.get("name")))
    for check in export.get("cross_checks") or []:
        if check.get("passed") is False:
            reasons.append(check.get("details") or str(check.get("name")))
    for group in export.get("missing_documents") or []:
        reasons.append("Missing: " + " or ".join(group))
    for edit in export.get("member_edits") or []:
        if edit.get("evidence") != "supports":
            reasons.append(
                f"The member typed {edit.get('typed_value')} for {edit.get('field')}; "
                f"we read {edit.get('read_value') or 'nothing'}."
            )
    if not reasons and lane_reason:
        reasons.append(lane_reason)
    return list(dict.fromkeys(reasons))


def passed_items(export: dict[str, Any]) -> list[str]:
    """Rules and checks that passed: shown only behind "Show all checks"."""
    decision = export.get("decision") or {}
    items = [
        r.get("reason") or str(r.get("rule"))
        for r in decision.get("rule_results") or []
        if r.get("outcome") == "pass"
    ]
    items += [
        c.get("reason") or str(c.get("name"))
        for c in (export.get("invoice") or {}).get("checks") or []
        if c.get("passed") is True
    ]
    items += [
        c.get("details") or str(c.get("name"))
        for c in export.get("cross_checks") or []
        if c.get("passed") is True
    ]
    return items


def field_rows(export: dict[str, Any]) -> list[dict[str, Any]]:
    """Every read value of every document, from the export; a field the member typed or edited
    is marked, with the value we read next to it."""
    edits = {(e.get("document_id"), e.get("field")): e for e in export.get("member_edits") or []}
    rows: list[dict[str, Any]] = []
    for document in export.get("documents") or []:
        for field in document.get("fields") or []:
            edit = edits.get((document.get("document_id"), field.get("name")))
            typed = field.get("source") in ("member_typed", "member_confirmed") or edit is not None
            rows.append(
                {
                    "kind": document.get("kind"),
                    "name": field.get("name"),
                    "value": field.get("value"),
                    "typed": typed,
                    "read_value": None if edit is None else edit.get("read_value"),
                }
            )
    return rows
