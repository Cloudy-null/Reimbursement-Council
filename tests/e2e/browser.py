"""Pick a browser for Playwright.

The pinned Playwright's own Chromium is used when it is installed. Otherwise PLAYWRIGHT_CHROMIUM
(a path to chrome.exe), otherwise Microsoft Edge, which every Windows PC has. On the build PC
there was no disk space to download Playwright's Chromium (HANDOVER CHECK), so Edge is used.
"""

import os
import sys
from pathlib import Path
from typing import Any


def chromium_launch_options(default_path: str) -> dict[str, Any]:
    if Path(default_path).is_file():
        return {}
    chosen = os.environ.get("PLAYWRIGHT_CHROMIUM")
    if chosen and Path(chosen).is_file():
        return {"executable_path": chosen}
    if sys.platform == "win32":
        return {"channel": "msedge"}
    return {}
