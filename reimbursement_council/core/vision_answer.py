"""The local model's answer: the shape it must follow (sent to Ollama as the format) and the
strict parse (check 1 in core/vision_checks.py). Values are as printed. Pure."""

import json

from pydantic import ValidationError

from reimbursement_council.core.models.common import DocumentKind, Model

ITEM_TYPES = (
    "frame",
    "lenses",
    "contact_lenses",
    "eye_test",
    "consultation",
    "medicine",
    "lab_test",
    "dental",
    "other",
)


class VisionItem(Model):
    description: str
    quantity: str | None
    amount: str | None
    # What the line is, as the model sees it: a hint for brand names no alias matches.
    item_type: str = "other"


class VisionAnswer(Model):
    """The model's answer, values as printed. Any other shape is refused."""

    document_kind: DocumentKind
    provider_name: str | None
    vat_number: str | None
    date: str | None
    time: str | None
    patient_name: str | None
    subtotal: str | None
    vat_total: str | None
    total: str | None
    items: list[VisionItem]


def _nullable() -> dict[str, object]:
    return {"type": ["string", "null"]}


ANSWER_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "document_kind": {
            "type": "string",
            "enum": ["invoice", "receipt", "prescription", "medical_report", "other"],
        },
        **{
            name: _nullable()
            for name in VisionAnswer.model_fields
            if name not in {"document_kind", "items"}
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantity": _nullable(),
                    "amount": _nullable(),
                    "item_type": {"type": "string", "enum": list(ITEM_TYPES)},
                },
                "required": ["description", "quantity", "amount", "item_type"],
            },
        },
    },
    "required": list(VisionAnswer.model_fields),
}


def parse_answer(text: str) -> VisionAnswer | None:
    """The answer, or None when it is not valid JSON in the agreed shape (check 1)."""
    try:
        return VisionAnswer.model_validate(json.loads(text))
    except (ValueError, ValidationError):
        return None
