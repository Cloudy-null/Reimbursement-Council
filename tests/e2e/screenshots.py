"""Screenshots of every screen, desktop and phone, Arabic and English, into screenshots/.

Run: uv run --no-sync python -m tests.e2e.screenshots
It starts the real website (with OCR), makes one claim of each kind through the browser, then
photographs each screen in the four views. screenshots/ is not committed (.gitignore).
"""

import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from tests.e2e.browser import chromium_launch_options

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "screenshots"
VIEWS = {"desktop": {"width": 1280, "height": 900}, "phone": {"width": 390, "height": 844}}


def _port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _wait_ready(url: str) -> None:
    deadline = time.time() + 600
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/ready") as response:
                if json.loads(response.read())["ready"]:
                    return
        except OSError:
            pass
        time.sleep(2)
    raise RuntimeError("the website did not get ready")


def _claim(page: Page, url: str, demo: str, total: str | None = None) -> str:
    page.goto(f"{url}/")
    page.check("#consent")
    page.locator(f"button[name=demo][value={demo}]").click()
    page.wait_for_url("**/check**")
    claim_id = page.url.split("/claims/")[1].split("/")[0]
    if demo == "missing":
        return claim_id  # left on the check step
    if total is not None:
        page.fill("#f-total", total)
    page.locator("form[action$='/submit'] button[type=submit]").click()
    page.wait_for_url("**/claims/*?lang=en")
    return claim_id


def main() -> int:
    data = Path(tempfile.mkdtemp(prefix="rc-shots-"))
    url = f"http://127.0.0.1:{_port()}"
    port = url.rsplit(":", 1)[1]
    log = (data / "server.log").open("wb")
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "reimbursement_council.cli.main",
            "serve",
            "--port",
            port,
            "--data-dir",
            str(data),
        ],  # fmt: skip
        cwd=REPO,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_ready(url)
        OUT.mkdir(exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(**chromium_launch_options(p.chromium.executable_path))
            maker = browser.new_page()
            maker.set_default_timeout(180_000)
            approved = _claim(maker, url, "approve")
            mismatch = _claim(maker, url, "mismatch")
            to_person = _claim(maker, url, "edit", total="999.00")
            draft = _claim(maker, url, "missing")
            screens = {
                "1-new-claim": "/",
                "2-check-missing-document": f"/claims/{draft}/check",
                "3-result-approved": f"/claims/{approved}",
                "4-result-asked-to-fix": f"/claims/{mismatch}",
                "5-result-person": f"/claims/{to_person}",
                "6-review-queue": "/review",
                "7-review-card": f"/review/{to_person}",
                "8-numbers": "/metrics",
                "9-error-page": "/claims/no-such-claim",
            }
            count = 0
            for view, size in VIEWS.items():
                page = browser.new_page(viewport=size)  # type: ignore[arg-type]
                for lang in ("en", "ar"):
                    for name, path in screens.items():
                        page.goto(f"{url}{path}{'&' if '?' in path else '?'}lang={lang}")
                        page.screenshot(path=OUT / f"{name}-{view}-{lang}.png", full_page=True)
                        count += 1
                page.close()
            browser.close()
        print(f"{count} screenshots in {OUT}")
        return 0
    finally:
        server.terminate()
        server.wait(timeout=20)
        log.close()
        shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
