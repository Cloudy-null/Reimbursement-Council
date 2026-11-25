"""Test-wide setup."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from reimbursement_council.cli.data_dir import DATA_DIR_ENV


@pytest.fixture(autouse=True)
def private_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Commands default to a temporary data folder in tests: a test must never write the real
    data/reviewer/health.json (unit tests once benched the real AI reviewer, fix/monitor)."""
    folder = tmp_path_factory.mktemp("rc-data")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv(DATA_DIR_ENV, str(folder))
        yield folder
