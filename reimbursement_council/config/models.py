"""Shapes of config/*.yaml. Every number the app uses is declared here and set in YAML."""

__all__ = ["TEMPLATE_PLACEHOLDERS", "LanguageMessages", "MessageConfig"]

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from reimbursement_council.config.config_base import ConfigModel
from reimbursement_council.config.message_models import (
    TEMPLATE_PLACEHOLDERS,
    LanguageMessages,
    MessageConfig,
)
from reimbursement_council.core.decision.calibration import PlattParams
from reimbursement_council.core.models.common import (
    DocumentKind,
    FieldName,
    Halalas,
    Lane,
    MemberName,
    Score,
)
from reimbursement_council.core.models.reference import PriceListItem


class SubLimitConfig(ConfigModel):
    limit_halalas: Halalas
    services: list[str] = Field(min_length=1)


class TierConfig(ConfigModel):
    limits_halalas: dict[str, Halalas]
    copay_rate: dict[str, Score]
    copay_cap_halalas: Halalas | None = None
    sub_limits: dict[str, SubLimitConfig] = Field(default_factory=dict)


class PolicyConfig(ConfigModel):
    claim_window_days: int = Field(ge=1)
    vat_rate: Score
    local_utc_offset_hours: int = Field(ge=-12, le=14)
    exclusions: list[str]
    vat_covered: bool
    rule_sources: dict[str, str] = Field(default_factory=dict)
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


class CaseReviewerConfig(MemberConfig):
    """The AI case reviewer (decision 010). It can only send a claim to a person."""

    timeout_seconds: float = Field(gt=0)
    check_timeout_seconds: float = Field(gt=0)
    review_lanes: list[Lane]
    score_floor: Score
    disagreement_gap: Score
    min_cited_fields: int = Field(ge=0)
    max_reason_characters: int = Field(gt=0)
    golden_good_min_score: Score
    golden_bad_max_score: Score
    golden_pass_rate: Score
    monitor_window: int = Field(ge=1)
    monitor_min_votes: int = Field(ge=1)
    max_discarded_rate: Score
    min_score_spread: float = Field(ge=0.0)

    @model_validator(mode="after")
    def usable_limits(self) -> Self:
        if self.monitor_min_votes > self.monitor_window:
            raise ValueError("monitor_min_votes cannot be more than monitor_window")
        if self.golden_bad_max_score >= self.golden_good_min_score:
            raise ValueError("golden_bad_max_score must be below golden_good_min_score")
        return self


class MembersConfig(ConfigModel):
    document_checker: DocumentCheckerConfig
    coverage_checker: CoverageCheckerConfig
    price_checker: PriceCheckerConfig
    history_member: HistoryMemberConfig
    case_reviewer: CaseReviewerConfig

    @model_validator(mode="after")
    def usable_council(self) -> Self:
        # The case reviewer does not count: the council must be able to decide without it.
        if not any(
            config.enabled and config.weight > 0
            for name, config in self.in_order()
            if name != "case_reviewer"
        ):
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


class OcrConfig(ConfigModel):
    label_match_ratio: Score
    alias_match_ratio: Score
    pattern_miss_factor: Score
    heuristic_factor: Score
    row_overlap: Score
    use_gpu: bool
    min_date_year: int = Field(ge=1900)
    max_date_year: int = Field(le=2200)


class VisionConfig(ConfigModel):
    """Checks and confidences for the local model reader (decision.yaml, vision)."""

    field_confidence: Score
    agree_confidence: Score
    disagree_confidence: Score
    ground_ratio: Score
    vat_number_pattern: str
    future_days: int = Field(ge=0)
    parallel_ocr: bool


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
    paid_right_tolerance_halalas: Halalas
    gemini_reader_enabled: bool
    reader: Literal["easyocr", "qr_only", "ollama"]
    vision: VisionConfig
    two_readers_enabled: bool
    passed_check_confidence: Score
    member_confirmed_confidence: Score
    confirm_date_margin_days: int = Field(ge=0)
    cross_checks_enabled: bool
    ocr: OcrConfig
    members: MembersConfig

    @model_validator(mode="after")
    def only_built_features(self) -> Self:
        if self.calibration_enabled and self.calibration_method != "platt":
            raise ValueError("only platt calibration is built; isotonic is not built yet")
        if self.gemini_reader_enabled:
            raise ValueError("gemini reader is not built yet, keep gemini_reader_enabled false")
        return self


class DocumentsConfig(ConfigModel):
    """Which documents each benefit category needs, how a document type is recognized, and
    how strict the cross-document checks are (config/documents.yaml)."""

    required_by_category: dict[str, list[list[DocumentKind]]]
    kind_keywords: dict[DocumentKind, list[str]]
    kind_match_ratio: Score
    name_match_ratio: Score
    date_tolerance_days: int = Field(ge=0)
    cross_check_score_factor: Score
    provider_check_categories: list[str]
    unbacked_edit_confidence: Score
    max_upload_megabytes: int = Field(gt=0)
    max_pdf_pages: int = Field(gt=0)
    pdf_render_scale: float = Field(gt=0)
    max_pdf_pixels: int = Field(gt=0)
    max_files_per_upload: int = Field(gt=0)


class SyntheticConfig(ConfigModel):
    """How the synthetic claim generator mixes its claims (config/synthetic.yaml)."""

    qr_share: Score
    defect_weights: dict[str, int]

    @field_validator("defect_weights")
    @classmethod
    def weights_are_usable(cls, weights: dict[str, int]) -> dict[str, int]:
        if any(w < 0 for w in weights.values()) or not any(weights.values()):
            raise ValueError("defect weights must be 0 or more, and not all 0")
        return weights


class LocalModelConfig(ConfigModel):
    """The local Ollama model (config/local_model.yaml)."""

    url: str = Field(pattern=r"^https?://")
    model: str = Field(min_length=1)
    temperature: float = Field(ge=0.0, le=2.0)
    seed: int
    timeout_seconds: float = Field(gt=0)
    keep_alive: str
    num_ctx: int = Field(gt=0)
    num_predict: int = Field(gt=0)
    prompt_version: str = Field(min_length=1)
    reviewer_prompt_version: str = Field(min_length=1)
    max_image_side: int = Field(gt=0)
    cache_dir: str


class Settings(ConfigModel):
    policy: PolicyConfig
    local_model: LocalModelConfig
    documents: DocumentsConfig
    decision: DecisionConfig
    prices: dict[str, PriceListItem]
    messages: MessageConfig
    synthetic: SyntheticConfig
    config_version: str
    calibration: PlattParams | None = None
    gemini_api_key: str | None
    demo_mode: bool
