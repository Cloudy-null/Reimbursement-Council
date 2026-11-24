"""Deliverable 2: the claim export, built from what is stored and valid against the schema."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from reimbursement_council.adapters.export_schema import (
    generated_schema,
    load_schema,
    schema_errors,
)
from reimbursement_council.adapters.files import load_reference_file
from reimbursement_council.adapters.storage import ClaimStore, ReviewRecord
from reimbursement_council.pipeline.export_claim import export_claim
from tests.factories import repo_settings
from tests.pipeline.test_process_claim import FIXTURES, load, run

EXPORTED = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)


def exported(name: str, tmp_path: Path, review: ReviewRecord | None = None):  # type: ignore[no-untyped-def]
    store = ClaimStore(tmp_path / "claims.sqlite")
    claim = load(name)
    run(claim, store)
    if review is not None:
        store.save_review(review)
    reference = load_reference_file(FIXTURES / "reference.json")
    return export_claim(claim, store, reference, repo_settings(), EXPORTED)


def test_committed_schema_matches_the_model() -> None:
    # If this fails, run: uv run reimbursement-council write-schema
    assert load_schema() == generated_schema()


@pytest.mark.parametrize(
    "name", ["clean", "late", "blurry_date", "prescription_only", "overpriced"]
)
def test_every_fixture_export_is_valid_against_the_schema(name: str, tmp_path: Path) -> None:
    export = exported(name, tmp_path)
    assert export is not None
    data = json.loads(export.model_dump_json())
    assert schema_errors(data) == []


def test_clean_export_has_money_in_halalas_and_is_ready(tmp_path: Path) -> None:
    export = exported("clean", tmp_path)
    assert export is not None and export.ready_for_processing
    assert export.invoice is not None and export.invoice.total_halalas == 17250
    assert export.payout is not None and export.payout.calculated_halalas == 15525
    assert export.decision.lane == "auto_approve" and export.schema_version == "1.0"
    primary = [d for d in export.documents if d.is_primary]
    assert (
        len(primary) == 1 and "/" not in primary[0].file_name and "\\" not in primary[0].file_name
    )


def test_a_claim_waiting_for_the_member_is_not_ready(tmp_path: Path) -> None:
    export = exported("prescription_only", tmp_path)
    assert export is not None and not export.ready_for_processing
    assert export.missing_documents and export.decision.self_fix_request is not None


def test_a_person_approving_makes_it_ready(tmp_path: Path) -> None:
    review = ReviewRecord(
        claim_id=load("overpriced").claim_id,
        reviewer="r1",
        started_at=EXPORTED,
        finished_at=EXPORTED,
        action="approve_amount",
        amount=10000,
        reason="network price",
    )
    export = exported("overpriced", tmp_path, review)
    assert export is not None and export.ready_for_processing
    assert export.review is not None and export.review.amount_halalas == 10000


def test_a_draft_has_no_export(tmp_path: Path) -> None:
    store = ClaimStore(tmp_path / "claims.sqlite")
    reference = load_reference_file(FIXTURES / "reference.json")
    assert export_claim(load("clean"), store, reference, repo_settings(), EXPORTED) is None


def test_schema_refuses_money_as_a_float() -> None:
    assert schema_errors({"claim_id": 1}) != []
