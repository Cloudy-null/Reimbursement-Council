"""Member and reviewer messages in Arabic and English (config/messages.yaml)."""

from typing import Self

from pydantic import model_validator

from reimbursement_council.config.config_base import ConfigModel
from reimbursement_council.core.models.common import DocumentKind

TEMPLATE_PLACEHOLDERS = {
    "amount": "0.00",
    "requested": "0.00",
    "reason": "",
    "request": "",
    "claim_window_days": 0,
    "field": "",
    "documents": "",
}
"""Every value a member message template may use."""


class LaneMessages(ConfigModel):
    approved: str
    approved_partial: str
    rejected: str
    self_fix: str
    human_review: str


class RuleMessages(ConfigModel):
    late: str
    policy_inactive: str
    person_not_covered: str
    excluded_service: str
    duplicate: str
    multiple_patients: str
    member_edit: str


class RequestMessages(ConfigModel):
    retake_photo: str
    add_document: str
    confirm_field: str
    missing_document: str
    mismatch: str
    check_photo: str


class LanguageMessages(ConfigModel):
    lanes: LaneMessages
    rules: RuleMessages
    requests: RequestMessages
    fields: dict[str, str]
    documents: dict[DocumentKind, str]
    or_word: str


class MessageConfig(ConfigModel):
    en: LanguageMessages
    ar: LanguageMessages

    @model_validator(mode="after")
    def same_field_labels(self) -> Self:
        missing = set(self.en.fields) ^ set(self.ar.fields)
        if missing:
            raise ValueError(f"field labels must exist in both languages: {sorted(missing)}")
        missing = set(self.en.documents) ^ set(self.ar.documents)
        if missing:
            raise ValueError(f"document names must exist in both languages: {sorted(missing)}")
        return self

    @model_validator(mode="after")
    def known_placeholders(self) -> Self:
        """A typo like {amout} fails here at startup, not when a member gets a message."""
        for language_name, language in (("en", self.en), ("ar", self.ar)):
            for section_name, section in (
                ("lanes", language.lanes),
                ("rules", language.rules),
                ("requests", language.requests),
            ):
                for key, template in section.model_dump().items():
                    try:
                        template.format(**TEMPLATE_PLACEHOLDERS)
                    except (KeyError, IndexError, ValueError) as error:
                        raise ValueError(
                            f"{language_name}.{section_name}.{key}: bad placeholder {error}"
                        ) from error
        return self
