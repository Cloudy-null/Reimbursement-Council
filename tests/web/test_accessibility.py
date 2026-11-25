"""Accessibility pass (brief: every digital skill level, Arabic and English): every control has
a label, every image has alt text, every page says its language, text colors meet WCAG AA
contrast, and no text is smaller than 12px."""

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from reimbursement_council.web.context import HERE, WebContext
from tests.web.check_helpers import submit, upload

CSS = (HERE / "static" / "app.css").read_text(encoding="utf-8")
TEXT_PAIRS = [
    ("ink", "paper"), ("ink", "surface"), ("ink-muted", "paper"), ("ink-muted", "surface"),
    ("accent", "surface"), ("accent", "paper"), ("accent-ink", "accent"),
    ("lane-approve", "surface"), ("lane-selffix", "surface"), ("lane-review", "surface"),
    ("lane-reject", "surface"), ("lane-approve", "tint-approve"), ("lane-selffix", "tint-selffix"),
    ("lane-review", "tint-review"), ("lane-reject", "tint-reject"), ("ink", "tint-review"),
    ("confidence-low-ink", "confidence-low"), ("ink", "confidence-low"),
]  # fmt: skip


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.controls: list[str] = []
        self.label_for: set[str] = set()
        self.inside_label = 0
        self.unlabelled_inside: list[str] = []
        self.images_without_alt = 0
        self.lang: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang")
        if tag == "label":
            self.inside_label += 1
            if a.get("for"):
                self.label_for.add(a["for"] or "")
        if tag in ("input", "select", "textarea") and a.get("type") != "hidden":
            if self.inside_label:
                return
            self.controls.append(a.get("id") or "(no id)")
        if tag == "img" and a.get("alt") is None:
            self.images_without_alt += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "label":
            self.inside_label -= 1


def check(html: str) -> None:
    page = Page()
    page.feed(html)
    assert page.lang in ("en", "ar")
    assert [c for c in page.controls if c not in page.label_for] == []
    assert page.images_without_alt == 0


def pages(client: TestClient, lang: str) -> list[str]:
    claim_id, _ = upload(client, ("r.png", b"pharmacy"))
    q = f"?lang={lang}"
    check_page = client.get(f"/claims/{claim_id}/check{q}").text
    submit(client, claim_id)
    return [client.get(f"/{q}").text, check_page, client.get(f"/claims/{claim_id}{q}").text,
            client.get(f"/review/{claim_id}{q}").text, client.get(f"/review{q}").text,
            client.get(f"/claims/none{q}").text]  # fmt: skip


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_every_control_has_a_label_and_every_image_alt_text(
    web: tuple[TestClient, WebContext], lang: str
) -> None:
    for html in pages(web[0], lang):
        check(html)
        assert (f'lang="{lang}"' in html) and (('dir="rtl"' in html) == (lang == "ar"))


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})", block))


def _luminance(color: str) -> float:
    parts = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    parts = [p / 12.92 if p <= 0.03928 else ((p + 0.055) / 1.055) ** 2.4 for p in parts]
    return 0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted([_luminance(a), _luminance(b)], reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_text_colors_meet_wcag_aa(scheme: str) -> None:
    light = _tokens(CSS[CSS.index(":root {") : CSS.index("}")])
    dark_start = CSS.index("@media (prefers-color-scheme: dark)")
    dark = light | _tokens(CSS[dark_start : CSS.index("}", dark_start)])
    colors = light if scheme == "light" else dark
    low = [(a, b, round(_contrast(colors[a], colors[b]), 2)) for a, b in TEXT_PAIRS]
    assert [pair for pair in low if pair[2] < 4.5] == []


def test_no_text_is_smaller_than_12px() -> None:
    sizes = [int(size) for size in re.findall(r"font-size:\s*(\d+)px", CSS)]
    assert sizes and min(sizes) >= 12


def test_design_doc_has_the_same_review_color_as_the_css() -> None:
    design = (Path(__file__).resolve().parents[2] / "docs" / "DESIGN.md").read_text(
        encoding="utf-8"
    )
    review = _tokens(CSS[CSS.index(":root {") : CSS.index("}")])["lane-review"]
    assert f"| --lane-review | Human review | {review} |" in design
