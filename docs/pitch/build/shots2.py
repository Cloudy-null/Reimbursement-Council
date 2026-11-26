"""v2 screenshots: one tight element per prototype slide, English desktop, demo claims only.

A private server on a new data folder (no real claims), like shots.py. Only the reviewer health
file and the synthetic check-set run reports are copied in, so the numbers page is the real one.
Run from the repo root: uv run --no-sync python docs/pitch/build/shots2.py
"""

import html
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, str(Path.cwd()))
from tests.e2e.browser import chromium_launch_options  # noqa: E402

OUT = Path("D:/rc-tmp/pitch/shots2")
DATA = Path("D:/rc-tmp/pitch/data2")
PORT = 8018
URL = f"http://127.0.0.1:{PORT}"
SIZE = {"width": 1024, "height": 768}


def prepare() -> None:
    shutil.rmtree(DATA, ignore_errors=True)
    (DATA / "reviewer").mkdir(parents=True)
    shutil.copy("data/reviewer/health.json", DATA / "reviewer" / "health.json")
    runs = DATA / "sets" / "abl" / "check_v2"
    runs.mkdir(parents=True)
    for f in Path("data/sets/abl/check_v2").glob("*.json"):
        if not f.name.startswith("claim_"):
            shutil.copy(f, runs / f.name)


def wait_ready() -> None:
    deadline = time.time() + 1200
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{URL}/api/ready") as r:
                if json.loads(r.read())["ready"]:
                    return
        except OSError:
            pass
        time.sleep(3)
    raise RuntimeError("not ready")


def start(page: Page, demo: str) -> str:
    page.goto(f"{URL}/?lang=en")
    page.check("#consent")
    page.locator(f"button[name=demo][value={demo}]").click()
    page.wait_for_url("**/check**")
    return page.url.split("/claims/")[1].split("/")[0]


def send(page: Page) -> None:
    page.get_by_role("button", name="Send claim").first.click()
    page.wait_for_url("**/claims/*?lang=en")


def element(page: Page, selector: str, name: str) -> None:
    page.locator(selector).first.screenshot(path=OUT / f"{name}.png")
    print("shot", name, flush=True)


def region(page: Page, top: str, bottom: str, name: str, pad: int = 12) -> None:
    a = page.locator(top).first.bounding_box()
    b = page.locator(bottom).first.bounding_box()
    page.locator(top).first.scroll_into_view_if_needed()
    a = page.locator(top).first.bounding_box()
    b = page.locator(bottom).first.bounding_box()
    clip = {"x": a["x"] - pad, "y": a["y"] - pad, "width": a["width"] + 2 * pad,
            "height": b["y"] + b["height"] - a["y"] + 2 * pad}
    page.screenshot(path=OUT / f"{name}.png", clip=clip)
    print("shot", name, flush=True)


def render_export(page: Page, full: dict) -> None:
    inv = full["invoice"]
    item = inv["line_items"][0]
    keep = {
        "status": full["status"],
        "ready_for_processing": full["ready_for_processing"],
        "provider": {k: full["provider"][k] for k in ("name", "vat_number", "in_network")},
        "invoice": {
            "treatment_date": inv["treatment_date"],
            "currency": inv["currency"],
            "total_halalas": inv["total_halalas"],
            "line_items": [{k: item[k] for k in ("description", "service_code", "confidence")}],
        },
        "member_edits": [{k: e[k] for k in ("field", "read_value", "typed_value", "evidence")}
                         for e in full["member_edits"]],
        "payout": {k: full["payout"][k] for k in ("requested_halalas", "copay_halalas",
                                                   "calculated_halalas")},
        "decision": {"lane": full["decision"]["lane"], "p_good": round(full["decision"]["p_good"], 3)},
    }
    body = html.escape(json.dumps(keep, indent=2, ensure_ascii=False))
    page.set_content(
        "<html><body style='margin:0;background:#fff'>"
        "<div id='json' style='width:1240px;padding:18px 26px;font:19px/1.35 Consolas,monospace;"
        "color:#1d1d1f;column-count:2;column-gap:40px;column-rule:1px solid #e6e2f0'>"
        f"<pre style='margin:0'>{body}</pre></div></body></html>"
    )
    page.set_viewport_size({"width": 1300, "height": 900})
    element(page, "#json", "6-export")


def main() -> None:
    prepare()
    OUT.mkdir(exist_ok=True)
    log = (DATA / "server.log").open("wb")
    server = subprocess.Popen(
        [sys.executable, "-m", "reimbursement_council.cli.main", "serve", "--port", str(PORT),
         "--data-dir", str(DATA)],
        stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        wait_ready()
        print("ready", flush=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(**chromium_launch_options(p.chromium.executable_path))
            ctx = browser.new_context(viewport=SIZE, device_scale_factor=2)
            page = ctx.new_page()
            page.set_default_timeout(300_000)

            edit = start(page, "edit")
            element(page, "#read-fields", "1-read-fields")
            page.fill("#f-total", "999.00")
            send(page)

            start(page, "missing")
            element(page, "#missing", "2-choices")

            optical = start(page, "optical")
            element(page, "#estimate", "3-payout")
            send(page)

            for demo in ("mismatch", "blurry", "approve", "pdf"):
                claim = start(page, demo)
                send(page)
                page.request.post(f"{URL}/claims/{claim}/to-reviewer", form={"lang": "en"})
            page.request.post(f"{URL}/claims/{optical}/to-reviewer", form={"lang": "en"})

            page.goto(f"{URL}/review?lang=en")
            element(page, "table.numbers", "4-queue")
            page.goto(f"{URL}/review/{edit}?lang=en")
            region(page, "#why", "#claim-data div.typed", "5-why")

            page.goto(f"{URL}/claims/{edit}?lang=en")
            href = page.get_by_role("link", name="Download claim data (JSON)").get_attribute("href")
            full = page.request.get(f"{URL}{href}").json()
            page.goto(f"{URL}/metrics?lang=en")
            element(page, ".tiles", "7-tiles")
            render_export(page, full)
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=30)
        log.close()


if __name__ == "__main__":
    main()
