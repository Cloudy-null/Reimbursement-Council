"""What the member can fix, and what only a human can settle (spec 6.4, owner decision).

member_requests lists the self-fix asks in the order the spec gives: missing documents, then
documents that disagree, then a clearer photo for a money or hard rule field the member typed
with nothing to back it. human_reasons lists what goes to a reviewer: an edit that contradicts
the documents, a possible duplicate, and a typed field still unreadable after its retake.
"""

from collections.abc import Sequence

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import FieldEdit
from reimbursement_council.core.models.common import RULE_FIELDS
from reimbursement_council.core.models.decision import (
    CrossCheckResult,
    DocumentNeed,
    RuleResult,
    SelfFixRequest,
)

DUPLICATE_REASON = "Possible duplicate of a receipt in another claim. A person must check."


def _unbacked(edits: Sequence[FieldEdit]) -> list[FieldEdit]:
    """Typed money or hard rule fields with no evidence either way."""
    return [e for e in edits if e.evidence == "none" and e.field in RULE_FIELDS]


def member_requests(
    needs: Sequence[DocumentNeed],
    cross_checks: Sequence[CrossCheckResult],
    edits: Sequence[FieldEdit],
    retake_fields: Sequence[str],
    settings: Settings,
) -> list[SelfFixRequest]:
    english = settings.messages.en
    requests = [
        SelfFixRequest(kind="add_document", field=need.group[0], text=need.request.en)
        for need in needs
        if not need.satisfied and need.group
    ]
    for check in cross_checks:
        if check.passed is False:
            label = english.fields.get(check.field, check.field)
            text = english.requests.mismatch.format(field=label, documents="these documents")
            requests.append(SelfFixRequest(kind="confirm_field", field=check.field, text=text))
    for edit in _unbacked(edits):
        if edit.field not in retake_fields:
            label = english.fields.get(edit.field, edit.field)
            text = english.requests.retake_photo.format(field=label)
            requests.append(SelfFixRequest(kind="retake_photo", field=edit.field, text=text))
    return requests


def human_reasons(
    rule_results: Sequence[RuleResult],
    edits: Sequence[FieldEdit],
    retake_fields: Sequence[str],
) -> list[str]:
    reasons = [
        r.reason for r in rule_results if r.rule == "member_edit" and r.outcome == "not_sure"
    ]
    if any(r.rule == "duplicate" and r.outcome == "not_sure" for r in rule_results):
        reasons.append(DUPLICATE_REASON)
    for edit in _unbacked(edits):
        if edit.field in retake_fields:
            reasons.append(
                f"The {edit.field} could not be read even after a clearer photo; "
                f"the member typed {edit.typed_value}."
            )
    return reasons
