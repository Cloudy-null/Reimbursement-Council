"""Load and validate config/*.yaml and environment variables. The one place settings come from."""

import hashlib
import logging
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError

from reimbursement_council.config.models import (
    DecisionConfig,
    DocumentsConfig,
    MessageConfig,
    PolicyConfig,
    Settings,
    SyntheticConfig,
)
from reimbursement_council.core.decision.calibration import PlattParams
from reimbursement_council.core.models.reference import PriceListItem
from reimbursement_council.core.text import normalize_text

logger = logging.getLogger(__name__)

CONFIG_FILES = (
    "decision.yaml",
    "documents.yaml",
    "messages.yaml",
    "policy.yaml",
    "prices.yaml",
    "synthetic.yaml",
)
CALIBRATION_FILE = "calibration.yaml"
VERSION_LENGTH = 12
TRUE_WORDS = frozenset({"true", "1", "yes"})
FALSE_WORDS = frozenset({"false", "0", "no", ""})


class ConfigError(Exception):
    """A config file or env var is missing or wrong. The message names the file and key."""


def _read_yaml(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ConfigError(f"missing config file: {path.name} (looked in {path.parent})") from error
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError(f"{path.name}: not valid YAML: {error}") from error


def _describe(error: ValidationError) -> str:
    parts = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"])
        parts.append(f"{location}: {item['msg']}" if location else item["msg"])
    return "; ".join(parts)


def _validate[ModelT: BaseModel](model: type[ModelT], data: Any, file_name: str) -> ModelT:
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise ConfigError(f"{file_name}: {_describe(error)}") from error


def _load_prices(data: Any, policy: PolicyConfig) -> dict[str, PriceListItem]:
    try:
        items = TypeAdapter(list[PriceListItem]).validate_python(data)
    except ValidationError as error:
        raise ConfigError(f"prices.yaml: {_describe(error)}") from error
    prices: dict[str, PriceListItem] = {}
    for item in items:
        if item.service_code in prices:
            raise ConfigError(f"prices.yaml: duplicate service_code {item.service_code}")
        prices[item.service_code] = item
    alias_owner: dict[str, str] = {}
    for item in items:
        for alias in item.aliases:
            key = normalize_text(alias)
            owner = alias_owner.setdefault(key, item.service_code)
            if owner != item.service_code:
                raise ConfigError(
                    f"prices.yaml: alias {key!r} is used by both {owner} and {item.service_code}"
                )
    for item in items:
        for tier_name, tier in policy.tiers.items():
            if item.category not in tier.limits_halalas or item.category not in tier.copay_rate:
                raise ConfigError(
                    f"prices.yaml: category {item.category} of {item.service_code} "
                    f"has no limit or co-pay in policy.yaml tier {tier_name}"
                )
    return prices


class CalibrationFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: str
    a: float
    b: float
    fitted_on: str


def _load_calibration(config_dir: Path, decision: DecisionConfig) -> PlattParams | None:
    """config/calibration.yaml holds fitted Platt parameters; needed only when calibration is on."""
    path = config_dir / CALIBRATION_FILE
    if not path.is_file():
        if decision.calibration_enabled:
            raise ConfigError(
                f"calibration_enabled is true but {CALIBRATION_FILE} is missing; "
                "run fit-calibration first"
            )
        return None
    data = _validate(CalibrationFile, _read_yaml(path), CALIBRATION_FILE)
    return PlattParams(a=data.a, b=data.b)


def _config_version(config_dir: Path) -> str:
    digest = hashlib.sha256()
    for name in sorted((*CONFIG_FILES, CALIBRATION_FILE)):
        path = config_dir / name
        if path.is_file():
            digest.update(name.encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()[:VERSION_LENGTH]


def _demo_mode(env: Mapping[str, str]) -> bool:
    word = env.get("DEMO_MODE", "").strip().lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    raise ConfigError(f"DEMO_MODE must be true or false, got {word!r}")


def load_settings(config_dir: Path, env: Mapping[str, str] | None = None) -> Settings:
    """Read every config file and env var, validate them, and fail loudly on any bad value."""
    environment = os.environ if env is None else env
    policy = _validate(PolicyConfig, _read_yaml(config_dir / "policy.yaml"), "policy.yaml")
    decision = _validate(DecisionConfig, _read_yaml(config_dir / "decision.yaml"), "decision.yaml")
    messages = _validate(MessageConfig, _read_yaml(config_dir / "messages.yaml"), "messages.yaml")
    prices = _load_prices(_read_yaml(config_dir / "prices.yaml"), policy)
    documents = _validate(
        DocumentsConfig, _read_yaml(config_dir / "documents.yaml"), "documents.yaml"
    )
    for category in sorted({item.category for item in prices.values()}):
        if category not in documents.required_by_category:
            raise ConfigError(
                f"documents.yaml: category {category} from prices.yaml has no required documents"
            )
    synthetic = _validate(
        SyntheticConfig, _read_yaml(config_dir / "synthetic.yaml"), "synthetic.yaml"
    )
    calibration = _load_calibration(config_dir, decision)
    settings = Settings(
        calibration=calibration,
        policy=policy,
        documents=documents,
        decision=decision,
        prices=prices,
        messages=messages,
        synthetic=synthetic,
        config_version=_config_version(config_dir),
        gemini_api_key=environment.get("GEMINI_API_KEY") or None,
        demo_mode=_demo_mode(environment),
    )
    logger.info("loaded config version %s from %s", settings.config_version, config_dir)
    return settings
