"""What the member can fix, and what only a human can settle (spec 6.4, owner decision).

member_requests lists the self-fix asks in the order the spec gives: missing documents, then
documents that disagree, then a clearer photo for a money or hard rule field the member typed
with nothing to back it. human_reasons lists what goes to a reviewer: an edit that contradicts
the documents, a possible duplicate, a typed field still unclear after its photo request, and a
mismatch the member kept after being asked about it.

asked_fields (claim.retake_fields) are the fields the member was already asked about, by a
photo request or a mismatch. Each is asked only once; what is still wrong goes to a human.
"""

from collections.abc import Mapping, Sequence

from reimbursement_council.config.models import LanguageMessages, Settings
from reimbursement_council.core.models.claim import FieldEdit
from reimbursement_council.core.models.common import MONEY_FIELDS, RULE_FIELDS
from reimbursement_council.core.models.decision import (
    CrossCheckResult,
    DocumentNeed,
    RuleResult,
    SelfFixRequest,
)
from reimbursement_council.core.money import format_sar

DUPLICATE_REASON = "Possible duplicate of a receipt in another claim. A person must check."
ACCOUNT = "account"  # the patient check compares a document with the member's account


def _unbacked(edits: Sequence[FieldEdit]) -> list[FieldEdit]:
    """Typed money or hard rule fields with no evidence either way."""
    return [e for e in edits if e.evidence == "none" and e.field in RULE_FIELDS]


def _label(field: str, settings: Settings) -> str:
    return settings.messages.en.fields.get(field, field)


def shown_value(field: str, value: str) -> str:
    """A money field in riyals (it is stored in halalas); any other field as it is."""
    if field in MONEY_FIELDS and value.isdigit():
        return f"{format_sar(int(value))} SAR"
    return value


def document_label(language: LanguageMessages, name: str) -> str:
    """A document kind's name in this language, or a field label such as "your account"."""
    documents = {str(kind): label for kind, label in language.documents.items()}
    return documents.get(name) or language.fields.get(name, name)


def mismatch_documents(check: CrossCheckResult, kinds: Mapping[str, str]) -> list[str]:
    """The kinds that disagree, plus "account" for the patient check (it compares a document
    with the member's account)."""
    names = [kinds.get(document_id, "other") for document_id in check.document_ids]
    return [*names, ACCOUNT] if check.name == "patient_matches_account" else names


def member_requests(
    needs: Sequence[DocumentNeed],
    cross_checks: Sequence[CrossCheckResult],
    edits: Sequence[FieldEdit],
    asked_fields: Sequence[str],
    settings: Settings,
    kinds: Mapping[str, str] | None = None,
    rule_requests: Sequence[SelfFixRequest] = (),
) -> list[SelfFixRequest]:
    """kinds: document id to its kind, so a mismatch request can name the documents.
    rule_requests: Bupa FAQ document rules not met yet (they come first: the member must fix
    the document before anything else is judged)."""
    english = settings.messages.en
    requests = [
        request.model_copy(
            update={
                "text": english.requests.add_document.format(field=_label(request.field, settings))
            }
        )
        for request in rule_requests
        if request.field not in asked_fields
    ] + [
        SelfFixRequest(kind="add_document", field=need.group[0], text=need.request.en)
        for need in needs
        if not need.satisfied and need.group
    ]
    for check in cross_checks:
        if check.passed is False and check.field not in asked_fields:
            documents = mismatch_documents(check, kinds or {})
            names = " / ".join(document_label(english, d) for d in documents)
            text = english.requests.mismatch.format(
                field=_label(check.field, settings), documents=names
            )
            requests.append(
                SelfFixRequest(
                    kind="fix_mismatch", field=check.field, text=text, documents=documents
                )
            )
    for edit in _unbacked(edits):
        if edit.field in asked_fields:
            continue
        label = _label(edit.field, settings)
        if edit.read_value is None:
            text = english.requests.retake_photo.format(field=label)
            requests.append(SelfFixRequest(kind="retake_photo", field=edit.field, text=text))
        else:
            text = english.requests.check_photo.format(field=label)
            requests.append(SelfFixRequest(kind="check_photo", field=edit.field, text=text))
    unique: list[SelfFixRequest] = []
    for request in requests:
        if all((r.kind, r.field) != (request.kind, request.field) for r in unique):
            unique.append(request)
    return unique


def human_reasons(
    rule_results: Sequence[RuleResult],
    edits: Sequence[FieldEdit],
    cross_checks: Sequence[CrossCheckResult],
    asked_fields: Sequence[str],
    settings: Settings,
) -> list[str]:
    reasons = [
        r.reason for r in rule_results if r.rule == "member_edit" and r.outcome == "not_sure"
    ]
    if any(r.rule == "duplicate" and r.outcome == "not_sure" for r in rule_results):
        reasons.append(DUPLICATE_REASON)
    for edit in _unbacked(edits):
        if edit.field in asked_fields:
            reasons.append(
                f"The {_label(edit.field, settings)} is still not clear after a new photo; "
                f"the member typed {shown_value(edit.field, edit.typed_value)}."
            )
    for check in cross_checks:
        if check.passed is False and check.field in asked_fields:
            reasons.append(
                f"The {_label(check.field, settings)} still does not match across the documents "
                "after the member was asked about it."
            )
    unique: list[str] = []
    for reason in reasons:
        if reason not in unique:
            unique.append(reason)
    return unique
