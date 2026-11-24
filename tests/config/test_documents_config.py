from pathlib import Path
from typing import Any

import pytest

from reimbursement_council.config.loader import ConfigError, load_settings
from tests.config.test_loader import changed_config, set_key
from tests.factories import REPO_CONFIG


def test_documents_config_loads_from_repo() -> None:
    s = load_settings(REPO_CONFIG, env={})
    assert s.documents.required_by_category["pharmacy"] == [
        ["invoice", "receipt"],
        ["prescription"],
    ]
    assert s.documents.required_by_category["outpatient"] == [
        ["invoice", "receipt"],
        ["medical_report"],
    ]
    assert s.documents.date_tolerance_days == 0
    assert s.documents.provider_check_categories == ["outpatient", "dental"]
    assert s.documents.unbacked_edit_confidence < s.decision.hard_rule_confidence_floor
    assert s.decision.cross_checks_enabled is True


def test_documents_file_is_part_of_the_config_version(tmp_path: Path) -> None:
    changed = changed_config(tmp_path, "documents.yaml", set_key("name_match_ratio", value=0.7))
    assert (
        load_settings(changed, env={}).config_version
        != load_settings(REPO_CONFIG, env={}).config_version
    )


def test_every_price_category_has_required_documents(tmp_path: Path) -> None:
    def drop_lab(data: Any) -> Any:
        del data["required_by_category"]["lab"]
        return data

    with pytest.raises(ConfigError, match="lab"):
        load_settings(changed_config(tmp_path, "documents.yaml", drop_lab), env={})


def test_unknown_document_kind_rejected(tmp_path: Path) -> None:
    config = changed_config(
        tmp_path, "documents.yaml", set_key("required_by_category", "lab", value=[["photo"]])
    )
    with pytest.raises(ConfigError, match="documents.yaml"):
        load_settings(config, env={})


def test_document_names_exist_in_both_languages() -> None:
    s = load_settings(REPO_CONFIG, env={})
    kinds = {"invoice", "receipt", "prescription", "medical_report", "other"}
    assert set(s.messages.en.documents) == set(s.messages.ar.documents) >= kinds


def test_missing_document_and_mismatch_requests_fill_their_placeholders() -> None:
    s = load_settings(REPO_CONFIG, env={})
    text = s.messages.en.requests.missing_document.format(documents="a prescription")
    assert "a prescription" in text
    mismatch = s.messages.ar.requests.mismatch.format(field="التاريخ", documents="الوصفة")
    assert "التاريخ" in mismatch and "الوصفة" in mismatch


def test_member_edit_rule_has_a_message() -> None:
    s = load_settings(REPO_CONFIG, env={})
    assert s.messages.en.rules.member_edit and s.messages.ar.rules.member_edit
