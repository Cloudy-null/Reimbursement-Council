import json
from pathlib import Path

import pytest

from reimbursement_council.cli.main import main
from tests.factories import REPO_CONFIG


def test_make_receipts_writes_images_and_truths(tmp_path: Path) -> None:
    out = tmp_path / "set"
    assert (
        main(
            [
                "make-receipts",
                "--count",
                "4",
                "--seed",
                "3",
                "--out",
                str(out),
                "--config-dir",
                str(REPO_CONFIG),
            ]
        )
        == 0
    )
    assert len(list(out.glob("*.png"))) == 4
    truths = sorted(out.glob("*.truth.json"))
    assert len(truths) == 4
    truth = json.loads(truths[0].read_text(encoding="utf-8"))
    assert {"total", "items", "damage", "layout"} <= set(truth)


def test_make_receipts_same_seed_same_images(tmp_path: Path) -> None:
    for name in ("a", "b"):
        main(
            [
                "make-receipts",
                "--count",
                "2",
                "--seed",
                "9",
                "--out",
                str(tmp_path / name),
                "--config-dir",
                str(REPO_CONFIG),
            ]
        )
    first = sorted((tmp_path / "a").glob("*.png"))
    second = sorted((tmp_path / "b").glob("*.png"))
    assert [p.read_bytes() for p in first] == [p.read_bytes() for p in second]


def test_read_accuracy_with_qr_only_reader(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "set"
    main(
        [
            "make-receipts",
            "--count",
            "3",
            "--seed",
            "5",
            "--out",
            str(out),
            "--qr-share",
            "1.0",
            "--damage",
            "none",
            "--config-dir",
            str(REPO_CONFIG),
        ]
    )
    code = main(
        [
            "read-accuracy",
            str(out),
            "--reader",
            "qr_only",
            "--config-dir",
            str(REPO_CONFIG),
            "--ocr-cache",
            str(tmp_path / "cache"),
        ]
    )
    printed = capsys.readouterr().out
    assert code == 0
    report = json.loads((out / "accuracy.json").read_text(encoding="utf-8"))
    assert report["summary"]["total"] == 1.0 and report["summary"]["qr"] == 1.0
    assert report["summary"]["receipts"] == 3
    assert "total" in printed
