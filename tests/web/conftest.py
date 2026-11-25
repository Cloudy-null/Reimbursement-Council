"""Fixtures for the web tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from reimbursement_council.adapters.storage import ClaimStore
from reimbursement_council.synthetic.claims import make_claim_set
from reimbursement_council.web.app import create_app
from reimbursement_council.web.context import WebContext
from tests.factories import settings_with
from tests.web.check_helpers import FakeReader


@pytest.fixture
def web(tmp_path: Path) -> tuple[TestClient, WebContext]:
    settings = settings_with(reader="qr_only")
    ctx = WebContext(
        settings=settings,
        reference=make_claim_set(7, 0, settings).reference,
        store=ClaimStore(tmp_path / "web.sqlite"),
        reader_for=lambda document: FakeReader(),
        uploads=tmp_path / "uploads",
        samples=tmp_path / "samples",
        results_root=tmp_path / "results",
    )
    return TestClient(create_app(ctx)), ctx
