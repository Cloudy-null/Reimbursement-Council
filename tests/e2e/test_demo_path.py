"""Playwright end to end test of the demo path, in a real browser against a real server with
the real OCR (brief deliverable 1: a working website, not mockups).

member uploads (demo claim) -> check step -> send -> asked to fix -> sends the right report ->
check -> send -> decided; a second claim with a changed total -> a person -> reviewer decides;
the claim data downloads as JSON valid against the schema.

Slow (EasyOCR on CPU, about two minutes). Run it with: uv run pytest -m e2e
"""

import json
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
pytest.importorskip("easyocr")

from reimbursement_council.adapters.export_schema import schema_errors  # noqa: E402

pytestmark = pytest.mark.e2e
REPO = Path(__file__).resolve().parents[2]
START_SECONDS = 120


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[str, Path]]:
    data = tmp_path_factory.mktemp("data")
    port = _free_port()
    command = [sys.executable, "-m", "reimbursement_council.cli.main", "serve",
               "--port", str(port), "--data-dir", str(data)]  # fmt: skip
    process = subprocess.Popen(command, cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + START_SECONDS
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                break
        except OSError:
            time.sleep(0.5)
    else:
        process.kill()
        raise RuntimeError("the server did not start")
    yield url, data
    process.terminate()
    process.wait(timeout=20)


@pytest.fixture(scope="module")
def page(server: tuple[str, Path]) -> Iterator["playwright.Page"]:
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(accept_downloads=True)
        tab = context.new_page()
        tab.set_default_timeout(180_000)  # the first OCR read loads the model
        yield tab
        browser.close()


def start_demo(page: "playwright.Page", url: str, label: str) -> None:
    page.goto(f"{url}/")
    page.check("#consent")
    page.get_by_role("button", name=label).click()
    page.wait_for_url("**/check**")


def lane(page: "playwright.Page") -> str:
    classes = page.locator("section.result").first.get_attribute("class") or ""
    return next(c.removeprefix("lane-") for c in classes.split() if c.startswith("lane-"))


def test_member_fixes_a_mismatch_and_the_claim_is_decided(
    page: "playwright.Page", server: tuple[str, Path]
) -> None:
    url, data = server
    start_demo(page, url, "Report for another patient")
    assert page.get_by_text("These do not match").is_visible()
    page.get_by_role("button", name="Send claim").click()
    page.wait_for_url("**/claims/*?lang=en")
    assert lane(page) == "self_fix"
    fix = next((data / "web" / "samples" / "demo").glob("*/mismatch/fix/report-right-patient.png"))
    page.set_input_files("#fix-photos", str(fix))
    page.select_option("#replace", index=2)  # 2. the report with the wrong patient
    page.get_by_role("button", name="Send the new photo").click()
    page.wait_for_url("**/check**")
    assert page.get_by_text("These do not match").count() == 0
    page.get_by_role("button", name="Send claim").click()
    page.wait_for_url("**/claims/*?lang=en")
    assert lane(page) in ("auto_approve", "human_review")


def test_changed_total_goes_to_a_person_who_decides_and_the_data_downloads(
    page: "playwright.Page", server: tuple[str, Path]
) -> None:
    url, _ = server
    start_demo(page, url, "Change the total (a person decides)")
    page.fill("#f-total", "999.00")
    page.get_by_role("button", name="Send claim").click()
    page.wait_for_url("**/claims/*?lang=en")
    assert lane(page) == "human_review"
    claim_id = page.url.split("/claims/")[1].split("?")[0]

    with page.expect_download() as download:
        page.get_by_role("link", name="Download claim data (JSON)").click()
    data = json.loads(Path(download.value.path()).read_text(encoding="utf-8"))
    assert data["claim_id"] == claim_id and schema_errors(data) == []
    assert any(e["evidence"] == "contradicts" for e in data["member_edits"])

    page.goto(f"{url}/review/{claim_id}")
    assert page.get_by_text("999.00").first.is_visible()
    page.fill("#reason", "QR code shows the real total")
    page.get_by_role("button", name="Reject").click()
    page.goto(f"{url}/review")
    assert page.locator(f"a[href*='{claim_id}']").count() == 0
