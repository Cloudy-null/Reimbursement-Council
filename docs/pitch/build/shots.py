"""Fresh English desktop screenshots of demo claims for the pitch deck.

Runs a private server on a new data folder (no real claims in it), copies only the reviewer
health file and the synthetic check-set run reports so the numbers page is the real one.
Run from the repo root: uv run --no-sync python D:/rc-tmp/pitch/shots.py
"""

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

OUT = Path("D:/rc-tmp/pitch/shots")
DATA = Path("D:/rc-tmp/pitch/data")
PORT = 8017
URL = f"http://127.0.0.1:{PORT}"
SIZE = {"width": 1280, "height": 800}


def prepare() -> None:
    shutil.rmtree(DATA, ignore_errors=True)
    (DATA / "reviewer").mkdir(parents=True)
    shutil.copy("data/reviewer/health.json", DATA / "reviewer" / "health.json")
    runs = DATA / "sets" / "abl" / "check_v2"
    runs.mkdir(parents=True)
    for f in Path("data/sets/abl/check_v2").glob("*.json"):
        if not f.name.startswith("claim_"):
            shutil.copy(f, runs / f.name)
    real = DATA / "real" / "sroie"
    real.mkdir(parents=True)
    for f in Path("data/real/sroie").glob("accuracy*.json"):
        shutil.copy(f, real / f.name)


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


def shot(page: Page, name: str, selector: str | None = None) -> None:
    if selector:
        page.locator(selector).first.scroll_into_view_if_needed()
        page.evaluate(
            "s => { const e = document.querySelector(s); window.scrollTo(0, e.getBoundingClientRect().top + window.scrollY - 24); }",
            selector,
        )
    page.screenshot(path=OUT / f"{name}.png")
    print("shot", name, flush=True)


def render_export(page: Page, full: dict) -> None:
    inv = full["invoice"]
    item = inv["line_items"][0]
    keep = {
        "schema_version": full["schema_version"],
        "status": full["status"],
        "ready_for_processing": full["ready_for_processing"],
        "categories": full["categories"],
        "provider": {k: full["provider"][k] for k in ("name", "vat_number", "in_network")},
        "invoice": {
            "treatment_date": inv["treatment_date"],
            "currency": inv["currency"],
            "vat_total_halalas": inv["vat_total_halalas"],
            "total_halalas": inv["total_halalas"],
            "line_items": [{k: item[k] for k in ("description", "service_code", "amount_halalas", "confidence")}],
        },
        "member_edits": [{k: e[k] for k in ("field", "read_value", "typed_value", "evidence")} for e in full["member_edits"]],
        "payout": {k: full["payout"][k] for k in ("requested_halalas", "copay_halalas", "calculated_halalas")},
        "decision": {"lane": full["decision"]["lane"], "p_good": round(full["decision"]["p_good"], 3)},
        "rule_sources": {"vat_excluded": full["rule_sources"]["vat_excluded"]},
    }
    import html
    body = html.escape(json.dumps(keep, indent=2, ensure_ascii=False))
    page.set_content(
        "<html><body style='margin:0;background:#fff'><div style='padding:20px 28px;font:15px/1.38 Consolas,monospace;color:#1d1d1f'>"
        "<div style='font:600 16px Segoe UI,sans-serif;color:#555;margin-bottom:8px'>claim export (excerpt), valid against schemas/claim-export.schema.json</div>"
        f"<pre style='margin:0;white-space:pre-wrap'>{body}</pre></div></body></html>"
    )
    page.screenshot(path=OUT / "7-export.png", full_page=True)
    print("shot 7-export", flush=True)


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

            page.goto(f"{URL}/?lang=en")
            page.check("#consent")
            shot(page, "1-upload")

            edit = start(page, "edit")
            shot(page, "2-check-read-first")
            page.fill("#f-total", "999.00")
            send(page)

            start(page, "missing")
            shot(page, "3-missing", "#missing")

            optical = start(page, "optical")
            shot(page, "4-optical-estimate", "#estimate")
            send(page)

            for demo in ("mismatch", "blurry", "approve", "pdf"):
                claim = start(page, demo)
                send(page)
                page.request.post(f"{URL}/claims/{claim}/to-reviewer", form={"lang": "en"})
            page.request.post(f"{URL}/claims/{optical}/to-reviewer", form={"lang": "en"})

            page.goto(f"{URL}/review?lang=en")
            shot(page, "5-queue")
            page.goto(f"{URL}/review/{edit}?lang=en")
            shot(page, "6-card")

            export = page.request.get(f"{URL}/claims/{edit}/export.json")
            if not export.ok:
                page.goto(f"{URL}/claims/{edit}?lang=en")
                href = page.get_by_role("link", name="Download claim data (JSON)").get_attribute("href")
                export = page.request.get(f"{URL}{href}")
            full = export.json()
            (OUT / "export.json").write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")
            render_export(page, full)
            page.goto(f"{URL}/metrics?lang=en")
            shot(page, "8-numbers")
            page.goto("file:///C:/Users/Cloudy/Desktop/Reimbursement-Council/docs/pitch/damage_chart.svg")
            page.locator("svg").screenshot(path=OUT / "damage_chart.png")
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=30)
        log.close()


if __name__ == "__main__":
    main()
