"""Shapes of config/*.yaml. Every number the app uses is declared here and set in YAML."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from reimbursement_council.core.models.common import FieldName, Halalas, MemberName, Score
from reimbursement_council.core.models.reference import PriceListItem


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TierConfig(ConfigModel):
    limits_halalas: dict[str, Halalas]
    copay_rate: dict[str, Score]


class PolicyConfig(ConfigModel):
    claim_window_days: int = Field(ge=1)
    vat_rate: Score
    local_utc_offset_hours: int = Field(ge=-12, le=14)
    exclusions: list[str]
    tiers: dict[str, TierConfig]


class MemberConfig(ConfigModel):
    enabled: bool
    weight: float = Field(ge=0.0)


class DocumentCheckerConfig(MemberConfig):
    required_fields: list[FieldName] = Field(min_length=1)
    failed_check_score_cap: Score


class CoverageCheckerConfig(MemberConfig):
    no_items_score: Score


class PriceCheckerConfig(MemberConfig):
    zero_score_ratio: float = Field(gt=1.0)
    unknown_item_score: Score


class HistoryMemberConfig(MemberConfig):
    min_past_claims: int = Field(ge=1)
    provider_trust_weight: Score


class MembersConfig(ConfigModel):
    document_checker: DocumentCheckerConfig
    coverage_checker: CoverageCheckerConfig
    price_checker: PriceCheckerConfig
    history_member: HistoryMemberConfig
    case_reviewer: MemberConfig

    @model_validator(mode="after")
    def usable_council(self) -> Self:
        if self.case_reviewer.enabled:
            raise ValueError("case_reviewer is not built yet, keep it disabled")
        if not any(config.enabled and config.weight > 0 for _, config in self.in_order()):
            raise ValueError("at least one council member must be enabled with weight above 0")
        return self

    def in_order(self) -> list[tuple[MemberName, MemberConfig]]:
        """Every member with its config, in the order of decision.yaml."""
        return [
            ("document_checker", self.document_checker),
            ("coverage_checker", self.coverage_checker),
            ("price_checker", self.price_checker),
            ("history_member", self.history_member),
            ("case_reviewer", self.case_reviewer),
        ]


class DecisionConfig(ConfigModel):
    hard_rule_confidence_floor: Score
    disagreement_limit: Score
    reviewer_time_value_halalas: Halalas
    qr_first_enabled: bool
    arithmetic_checks_enabled: bool
    arithmetic_tolerance_halalas: Halalas
    failed_check_confidence_factor: Score
    partial_payout_tolerance_halalas: Halalas
    calibration_enabled: bool
    calibration_method: Literal["platt", "isotonic"]
    disagreement_routing_enabled: bool
    cost_lanes_enabled: bool
    fixed_p_good_threshold: Score
    always_review_amount_enabled: bool
    always_review_amount_halalas: Halalas
    self_fix_enabled: bool
    self_fix_max_retries: int = Field(ge=0)
    self_fix_p_good_limit: Score
    gemini_reader_enabled: bool
    members: MembersConfig

    @model_validator(mode="after")
    def only_built_features(self) -> Self:
        if self.calibration_enabled:
            raise ValueError("calibration is not built yet, keep calibration_enabled false")
        if self.gemini_reader_enabled:
            raise ValueError("gemini reader is not built yet, keep gemini_reader_enabled false")
        return self


TEMPLATE_PLACEHOLDERS = {
    "amount": "0.00",
    "requested": "0.00",
    "reason": "",
    "request": "",
    "claim_window_days": 0,
    "field": "",
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


class RequestMessages(ConfigModel):
    retake_photo: str
    add_document: str
    confirm_field: str


class LanguageMessages(ConfigModel):
    lanes: LaneMessages
    rules: RuleMessages
    requests: RequestMessages
    fields: dict[str, str]


class MessageConfig(ConfigModel):
    en: LanguageMessages
    ar: LanguageMessages

    @model_validator(mode="after")
    def same_field_labels(self) -> Self:
        missing = set(self.en.fields) ^ set(self.ar.fields)
        if missing:
            raise ValueError(f"field labels must exist in both languages: {sorted(missing)}")
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


class Settings(ConfigModel):
    policy: PolicyConfig
    decision: DecisionConfig
    prices: dict[str, PriceListItem]
    messages: MessageConfig
    config_version: str
    gemini_api_key: str | None
    demo_mode: bool
