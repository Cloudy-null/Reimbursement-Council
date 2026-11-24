import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from reimbursement_council.config.loader import ConfigError, load_settings
from tests.factories import REPO_CONFIG

Mutate = Callable[[Any], Any]


def changed_config(tmp_path: Path, file_name: str, mutate: Mutate) -> Path:
    """Copy the repo config to tmp_path and change one file."""
    config_dir = tmp_path / "config"
    shutil.copytree(REPO_CONFIG, config_dir)
    path = config_dir / file_name
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data = mutate(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return config_dir


def set_key(*keys: str, value: Any) -> Mutate:
    def mutate(data: Any) -> Any:
        target = data
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = value
        return data

    return mutate


def test_repo_config_loads() -> None:
    s = load_settings(REPO_CONFIG, env={})
    assert s.decision.reviewer_time_value_halalas == 2500
    assert s.prices["CONS-GP"].network_price == 15000
    assert len(s.config_version) == 12
    assert s.gemini_api_key is None and s.demo_mode is False
    assert s.policy.tiers["silver"].copay_rate["outpatient"] == 0.10
    assert s.messages.ar.fields["treatment_date"] == "تاريخ العلاج"


def test_env_read_in_one_place() -> None:
    s = load_settings(REPO_CONFIG, env={"GEMINI_API_KEY": "k", "DEMO_MODE": "true"})
    assert s.gemini_api_key == "k" and s.demo_mode is True


def test_bad_demo_mode_rejected() -> None:
    with pytest.raises(ConfigError, match="DEMO_MODE"):
        load_settings(REPO_CONFIG, env={"DEMO_MODE": "maybe"})


def test_config_version_changes_with_content(tmp_path: Path) -> None:
    changed = changed_config(tmp_path, "decision.yaml", set_key("disagreement_limit", value=0.3))
    assert (
        load_settings(changed, env={}).config_version
        != load_settings(REPO_CONFIG, env={}).config_version
    )


def test_unknown_key_rejected(tmp_path: Path) -> None:
    def typo(data: Any) -> Any:
        data["reviewer_time_valu_halalas"] = data.pop("reviewer_time_value_halalas")
        return data

    with pytest.raises(ConfigError, match=r"decision\.yaml.*reviewer_time_valu_halalas"):
        load_settings(changed_config(tmp_path, "decision.yaml", typo), env={})


def test_floor_above_one_rejected(tmp_path: Path) -> None:
    config = changed_config(
        tmp_path, "decision.yaml", set_key("hard_rule_confidence_floor", value=1.5)
    )
    with pytest.raises(ConfigError, match="hard_rule_confidence_floor"):
        load_settings(config, env={})


def test_negative_weight_rejected(tmp_path: Path) -> None:
    config = changed_config(
        tmp_path, "decision.yaml", set_key("members", "price_checker", "weight", value=-1.0)
    )
    with pytest.raises(ConfigError, match=r"members\.price_checker\.weight"):
        load_settings(config, env={})


def test_no_enabled_member_rejected(tmp_path: Path) -> None:
    def all_off(data: Any) -> Any:
        for member in data["members"].values():
            member["enabled"] = False
        return data

    with pytest.raises(ConfigError, match="at least one council member"):
        load_settings(changed_config(tmp_path, "decision.yaml", all_off), env={})


def test_case_reviewer_not_built_yet(tmp_path: Path) -> None:
    config = changed_config(
        tmp_path, "decision.yaml", set_key("members", "case_reviewer", "enabled", value=True)
    )
    with pytest.raises(ConfigError, match="case_reviewer is not built yet"):
        load_settings(config, env={})


def test_calibration_needs_its_file(tmp_path: Path) -> None:
    config = changed_config(tmp_path, "decision.yaml", set_key("calibration_enabled", value=True))
    (config / "calibration.yaml").unlink(missing_ok=True)  # the repo now has a fitted one
    with pytest.raises(ConfigError, match=r"calibration\.yaml"):
        load_settings(config, env={})


def test_calibration_file_loads_when_enabled(tmp_path: Path) -> None:
    config = changed_config(tmp_path, "decision.yaml", set_key("calibration_enabled", value=True))
    params = "method: platt\na: 8.0\nb: -5.0\nfitted_on: test\n"
    (config / "calibration.yaml").write_text(params, encoding="utf-8")
    s = load_settings(config, env={})
    assert s.calibration is not None and s.calibration.a == 8.0


def test_gemini_reader_not_built_yet(tmp_path: Path) -> None:
    config = changed_config(tmp_path, "decision.yaml", set_key("gemini_reader_enabled", value=True))
    with pytest.raises(ConfigError, match="gemini reader is not built yet"):
        load_settings(config, env={})


def test_price_category_missing_from_tier_rejected(tmp_path: Path) -> None:
    def new_category(data: Any) -> Any:
        data[0]["category"] = "optical"
        return data

    with pytest.raises(ConfigError, match=r"optical.*silver"):
        load_settings(changed_config(tmp_path, "prices.yaml", new_category), env={})


def test_duplicate_service_code_rejected(tmp_path: Path) -> None:
    def duplicate(data: Any) -> Any:
        data[1]["service_code"] = data[0]["service_code"]
        return data

    with pytest.raises(ConfigError, match=r"prices\.yaml.*CONS-GP"):
        load_settings(changed_config(tmp_path, "prices.yaml", duplicate), env={})


def test_messages_languages_must_have_same_keys(tmp_path: Path) -> None:
    def drop_label(data: Any) -> Any:
        del data["ar"]["fields"]["receipt"]
        return data

    with pytest.raises(ConfigError, match=r"messages\.yaml.*receipt"):
        load_settings(changed_config(tmp_path, "messages.yaml", drop_label), env={})


def test_missing_lane_message_rejected(tmp_path: Path) -> None:
    def drop_lane(data: Any) -> Any:
        del data["en"]["lanes"]["self_fix"]
        return data

    with pytest.raises(ConfigError, match=r"messages\.yaml.*self_fix"):
        load_settings(changed_config(tmp_path, "messages.yaml", drop_lane), env={})


def test_missing_config_file_names_it(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    shutil.copytree(REPO_CONFIG, config_dir)
    (config_dir / "policy.yaml").unlink()
    with pytest.raises(ConfigError, match=r"policy\.yaml"):
        load_settings(config_dir, env={})


def test_bad_yaml_names_the_file(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    shutil.copytree(REPO_CONFIG, config_dir)
    (config_dir / "decision.yaml").write_text("members: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError, match=r"decision\.yaml"):
        load_settings(config_dir, env={})


def test_template_placeholder_typo_rejected(tmp_path: Path) -> None:  # final review
    config = changed_config(
        tmp_path,
        "messages.yaml",
        set_key("en", "lanes", "approved", value="We will send you {amout} SAR."),
    )
    with pytest.raises(ConfigError, match=r"messages\.yaml.*amout"):
        load_settings(config, env={})


def test_rule_fields_have_labels() -> None:  # final review: raw "line_items" in Arabic text
    s = load_settings(REPO_CONFIG, env={})
    for language in (s.messages.en, s.messages.ar):
        assert {"line_items", "treatment_date", "receipt", "patient_name"} <= set(language.fields)


def test_aliases_load_and_belong_to_one_code() -> None:
    s = load_settings(REPO_CONFIG, env={})
    assert "كشف عام" in s.prices["CONS-GP"].aliases
    assert s.prices["XRAY-CHEST"].category == "radiology"


def test_shared_alias_rejected(tmp_path: Path) -> None:
    def share(data: Any) -> Any:
        data[1]["aliases"] = data[1]["aliases"] + ["Consultation"]
        return data

    with pytest.raises(ConfigError, match=r"prices\.yaml.*consultation"):
        load_settings(changed_config(tmp_path, "prices.yaml", share), env={})
