import json
from collections import Counter
from pathlib import Path

from reimbursement_council.cli.main import main
from reimbursement_council.synthetic.language_content import LANGUAGES
from tests.factories import REPO_CONFIG


def test_language_set_has_every_language_with_its_supported_flag(tmp_path: Path) -> None:
    out = tmp_path / "languages"
    command = ["make-language-set", str(out), "--seed", "2", "--per-language", "2"]
    assert main([*command, "--config-dir", str(REPO_CONFIG)]) == 0
    images = sorted(out.glob("receipt_2_*.png"))
    assert len(images) == 2 * len(LANGUAGES)
    truths = [
        json.loads(image.with_suffix("").with_suffix(".truth.json").read_text(encoding="utf-8"))
        for image in images
    ]
    assert Counter(t["language"] for t in truths) == dict.fromkeys(LANGUAGES, 2)
    for truth in truths:
        assert truth["supported"] is (truth["language"] not in ("french", "urdu"))
        assert truth["layout"] == truth["language"] and truth["damage"] == "none"
    manifest = json.loads((out / "set.json").read_text(encoding="utf-8"))
    assert manifest["count"] == len(images)
    assert manifest["languages"]["urdu"] is False and manifest["languages"]["hijri_date"] is True
