"""The default data folder for commands: data/, or RC_DATA_DIR when set (tests point it at a
temporary folder, so a test run never writes the real reviewer health file)."""

import os
from pathlib import Path

DATA_DIR_ENV = "RC_DATA_DIR"


def default_data_dir() -> Path:
    return Path(os.environ.get(DATA_DIR_ENV) or "data")
