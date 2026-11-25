import json
import urllib.error
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from reimbursement_council.adapters.case_reviewer_model import (
    LocalCaseReviewer,
    ReviewerTimeoutError,
)
from reimbursement_council.adapters.golden_set import load_golden_set
from reimbursement_council.adapters.local_model import LocalModelError
from reimbursement_council.adapters.reviewer_health_store import ReviewerHealthStore
from reimbursement_council.core.models.case_review import ReviewerHealth
from tests.factories import repo_settings


def test_reviewer_uses_its_own_short_timeout_and_no_images() -> None:
    calls: list[tuple[dict[str, Any], float]] = []

    def transport(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
        calls.append((body, timeout))
        return {"message": {"content": "{}"}}

    settings = repo_settings()
    reviewer = LocalCaseReviewer(settings.local_model, 7.5, transport)
    assert reviewer.review("p", "s", {"type": "object"}) == "{}"
    body, timeout = calls[0]
    assert timeout == 7.5
    assert body["options"]["temperature"] == 0.0
    assert body["format"] == {"type": "object"}
    assert body["messages"][0] == {"role": "system", "content": "s"}
    assert "images" not in body["messages"][-1]


@pytest.mark.parametrize(
    "cause", [TimeoutError("slow"), urllib.error.URLError(TimeoutError("slow"))]
)
def test_a_timeout_is_told_apart_from_other_errors(cause: Exception) -> None:
    def transport(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
        raise LocalModelError("no answer") from cause

    reviewer = LocalCaseReviewer(repo_settings().local_model, 1.0, transport)
    with pytest.raises(ReviewerTimeoutError):
        reviewer.review("p", "s", {})


def test_another_error_stays_a_model_error() -> None:
    def transport(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
        raise LocalModelError("refused") from ConnectionRefusedError()

    reviewer = LocalCaseReviewer(repo_settings().local_model, 1.0, transport)
    with pytest.raises(LocalModelError) as caught:
        reviewer.review("p", "s", {})
    assert not isinstance(caught.value, ReviewerTimeoutError)


def test_health_store_starts_unchecked_and_keeps_changes(tmp_path: Path) -> None:
    store = ReviewerHealthStore(tmp_path / "reviewer" / "health.json")
    assert store.load() == ReviewerHealth()
    store.update(lambda h: h.model_copy(update={"status": "healthy", "model": "m"}))
    again = ReviewerHealthStore(tmp_path / "reviewer" / "health.json")
    assert again.load().status == "healthy" and again.load().model == "m"


def test_an_unreadable_health_file_benches(tmp_path: Path) -> None:
    path = tmp_path / "health.json"
    path.write_text(json.dumps({"status": "healthy", "surprise": 1}), encoding="utf-8")
    health = ReviewerHealthStore(path).load()
    assert health.status == "benched" and health.benched_at is not None
    assert health.benched_at <= datetime.now(UTC)


def test_golden_set_has_twenty_cases_of_every_kind() -> None:
    cases = load_golden_set()
    assert len(cases) == 20
    kinds = {case.kind for case in cases}
    assert kinds == {"clear_good", "clear_bad", "tricky", "injection"}
    assert sum(case.kind == "injection" for case in cases) >= 3
    assert all(case.expected == "bad" for case in cases if case.kind == "injection")
    assert len({case.summary.claim_id for case in cases}) == 20


def test_a_bad_golden_file_stops_the_check(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="broken.json"):
        load_golden_set(tmp_path)
    with pytest.raises(FileNotFoundError):
        load_golden_set(tmp_path / "empty")
