"""AI case reviewer: check what the local model answered. Pure: the model call is in an adapter.

The model's answer is untrusted input. It is used only when it parses, matches the schema and
every cited field is a value we really read. Otherwise the answer is discarded (problem
"schema" or "citation") and the council decides without it. Even a used answer can only send
a claim to a person (core/decision/reviewer_guard.py).
"""

from typing import Any, Literal, get_args

from pydantic import Field, ValidationError

from reimbursement_council.config.models import CaseReviewerConfig
from reimbursement_council.core.council.case_reviewer_summary import without_fence_words
from reimbursement_council.core.models.case_review import (
    CaseReview,
    CitedField,
    ReviewProblem,
    ReviewSummary,
)
from reimbursement_council.core.models.common import MONEY_FIELDS, FieldName, Model, Score
from reimbursement_council.core.models.decision import Vote
from reimbursement_council.core.money import parse_sar_to_halalas

MEMBER = "case_reviewer"
FIELD_NAMES: tuple[str, ...] = get_args(FieldName)


class ReviewerAnswer(Model):
    score: Score
    reason: str = Field(min_length=1)
    cited_fields: list[CitedField]


def answer_schema(config: CaseReviewerConfig) -> dict[str, Any]:
    """The JSON Schema the model must follow (sent to Ollama as the format)."""
    return {
        "type": "object",
        "properties": {
            "score": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
            "cited_fields": {
                "type": "array",
                "minItems": config.min_cited_fields,
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "enum": list(FIELD_NAMES)},
                        "value": {"type": "string"},
                    },
                    "required": ["name", "value"],
                },
            },
        },
        "required": ["score", "reason", "cited_fields"],
    }


def _plain(text: str) -> str:
    return " ".join(without_fence_words(text).split()).casefold()


def _same_text(a: str, b: str) -> bool:
    """Equal ignoring spaces and case, and fence words the prompt replaced."""
    return _plain(a) == _plain(b)


def cited_value_matches(name: str, cited: str, read: str) -> bool:
    """Money is compared as numbers (172.5 matches 172.50); other text ignoring spaces and
    case. Both sides of a money field are SAR text, as in the summary."""
    if name in MONEY_FIELDS:
        cited_halalas = parse_sar_to_halalas(cited)
        read_halalas = parse_sar_to_halalas(read)
        return cited_halalas is not None and cited_halalas == read_halalas
    return _same_text(cited, read)


def bad_citations(cited: list[CitedField], summary: ReviewSummary) -> list[str]:
    """Every cited field that is not in the summary with that value, as plain text."""
    bad: list[str] = []
    for field in cited:
        read = [f.value for f in summary.fields if f.name == field.name]
        if not read:
            bad.append(f"{field.name} was not read")
        elif not any(cited_value_matches(field.name, field.value, value) for value in read):
            bad.append(f"{field.name} {field.value!r} is not the read value")
    return bad


def _parse(text: str, config: CaseReviewerConfig) -> ReviewerAnswer | None:
    try:
        answer = ReviewerAnswer.model_validate_json(text, strict=True)
    except ValidationError:
        return None
    reason = " ".join(answer.reason.split())
    if len(reason) > config.max_reason_characters:
        return None
    if len(answer.cited_fields) < config.min_cited_fields:
        return None
    if any(field.name not in FIELD_NAMES for field in answer.cited_fields):
        return None
    return answer.model_copy(update={"reason": reason})


def check_answer(
    text: str, summary: ReviewSummary, config: CaseReviewerConfig, model: str, prompt_version: str
) -> CaseReview:
    """A used review (score set) or a discarded one with its problem."""
    answer = _parse(text, config)
    if answer is None:
        return discarded("schema", model, prompt_version, "The answer did not match the schema.")
    bad = bad_citations(answer.cited_fields, summary)
    if bad:
        return discarded(
            "citation",
            model,
            prompt_version,
            "The answer cited values we did not read: " + "; ".join(bad) + ".",
            reason=answer.reason,
            cited=answer.cited_fields,
        )
    return CaseReview(
        status="used",
        score=answer.score,
        weight=config.weight,
        reason=answer.reason,
        cited_fields=list(answer.cited_fields),
        model=model,
        prompt_version=prompt_version,
    )


def discarded(
    problem: ReviewProblem,
    model: str,
    prompt_version: str,
    effect: str,
    reason: str | None = None,
    cited: list[CitedField] | None = None,
) -> CaseReview:
    return CaseReview(
        status="discarded",
        problem=problem,
        reason=reason,
        cited_fields=list(cited or []),
        model=model,
        prompt_version=prompt_version,
        effect=effect,
    )


def not_used(
    status: Literal["skipped", "benched"],
    problem: ReviewProblem,
    model: str,
    prompt_version: str,
    effect: str,
) -> CaseReview:
    """A skipped or benched review: no answer was asked for or none came back."""
    return CaseReview(
        status=status, problem=problem, model=model, prompt_version=prompt_version, effect=effect
    )


def review_vote(review: CaseReview) -> Vote | None:
    """The review as a council vote, only when it was used."""
    if review.status != "used" or review.score is None:
        return None
    return Vote(
        member=MEMBER,
        score=review.score,
        weight=review.weight,
        reason=review.reason or "",
        evidence=[f.name for f in review.cited_fields],
    )
