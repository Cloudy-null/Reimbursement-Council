import json
from pathlib import Path

from PIL import Image

from reimbursement_council.cli.main import main
from tests.factories import REPO_CONFIG

CONFIG = ["--config-dir", str(REPO_CONFIG)]


def _truths(folder: Path) -> dict[str, dict[str, object]]:
    return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in folder.glob("*.truth.json")}


def test_damage_set_keeps_claims_and_truth(tmp_path: Path) -> None:
    source = tmp_path / "claims"
    assert main(["make-claims", "--count", "4", "--seed", "3", "--out", str(source), *CONFIG]) == 0
    out = tmp_path / "damaged"
    command = ["make-damage-set", str(source), str(out), "--kinds", "blur,rotation"]
    assert main([*command, "--levels", "1,5", *CONFIG]) == 0
    folders = sorted(p.name for p in out.iterdir())
    assert folders == ["blur_1", "blur_5", "rotation_1", "rotation_5"]
    before = _truths(source)
    for folder in out.iterdir():
        kind, level = folder.name.rsplit("_", 1)
        assert len(list(folder.glob("*.claim.json"))) == 4
        for path in source.glob("*.claim.json"):
            assert (folder / path.name).read_bytes() == path.read_bytes()
        after = _truths(folder)
        assert set(after) == set(before)
        for name, truth in after.items():
            assert truth.pop("damage_suite") == {"kind": kind, "level": int(level)}
            assert truth == before[name]
        manifest = json.loads((folder / "set.json").read_text(encoding="utf-8"))
        assert manifest["damage_suite"]["kind"] == kind and manifest["count"] == 4
        reference = (folder / "reference.json").read_bytes()
        assert reference == (source / "reference.json").read_bytes()
        for image in source.glob("*.png"):
            damaged = folder / image.name
            if "-fix" in image.name:  # the member's new photo stays clean
                assert damaged.read_bytes() == image.read_bytes()
            else:
                assert damaged.read_bytes() != image.read_bytes()
                assert Image.open(damaged).size == Image.open(image).size


def test_damage_set_works_on_a_sheet_set_and_refuses_bad_input(tmp_path: Path) -> None:
    source = tmp_path / "dental"
    assert main(["make-dental-claims", str(source), *CONFIG]) == 0
    out = tmp_path / "damaged"
    assert main(["make-damage-set", str(source), str(out), "--levels", "2", *CONFIG]) == 0
    assert len(list(out.iterdir())) == 10  # every kind in the config, one level
    assert main(["make-damage-set", str(source), str(out), *CONFIG]) == 2  # not empty
    assert main(["make-damage-set", str(tmp_path), str(tmp_path / "x"), *CONFIG]) == 2
    bad_level = ["make-damage-set", str(source), str(tmp_path / "y"), "--levels", "6"]
    assert main([*bad_level, *CONFIG]) == 2
