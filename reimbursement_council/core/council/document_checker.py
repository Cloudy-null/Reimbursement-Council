"""Document checker: how sure we are the document is valid and was read correctly.

Looks at the confidence of the required fields and at failed checks.
Asks the member to retake the photo for a missing field, or to confirm an unclear one.
"""

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.case import ClaimCase
from reimbursement_council.core.models.common import RequestKind
from reimbursement_council.core.models.decision import Vote

MEMBER = "document_checker"


def vote(case: ClaimCase, settings: Settings) -> Vote:
    config = settings.decision.members.document_checker
    floor = settings.decision.hard_rule_confidence_floor
    extraction = case.extraction
    if extraction is None:
        return Vote(
            member=MEMBER,
            score=0.0,
            reason="No receipt or invoice in the claim.",
            evidence=[],
            request="Please add the receipt.",
            request_kind="add_document",
            request_field="receipt",
        )

    confidences: list[float] = []
    request: tuple[str, RequestKind, str] | None = None
    for name in config.required_fields:
        field = extraction.best(name)
        confidences.append(0.0 if field is None else field.confidence)
        if request is not None:
            continue
        if field is None:
            request = (
                f"We could not read the {name}. Please retake the photo.",
                "retake_photo",
                name,
            )
        elif field.confidence < floor:
            request = (f"Please confirm the {name}.", "confirm_field", name)

    score = sum(confidences) / len(confidences)
    failed = [check.name for check in extraction.checks if not check.passed]
    if failed:
        score = min(score, config.failed_check_score_cap)
    reason = (
        f"Average confidence {score:.2f} on {', '.join(config.required_fields)}; "
        f"{len(failed)} check{'s' if len(failed) != 1 else ''} failed."
    )
    if request is None:
        return Vote(
            member=MEMBER, score=score, reason=reason, evidence=list(config.required_fields)
        )
    text, kind, field_name = request
    return Vote(
        member=MEMBER,
        score=score,
        reason=reason,
        evidence=list(config.required_fields),
        request=text,
        request_kind=kind,
        request_field=field_name,
    )
