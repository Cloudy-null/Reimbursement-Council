"""Write a damaged copy of a claim set folder (make-damage-set).

The copy has the same claim files, so the claims point at the damaged images by the same file
names. Only the documents the claims name are damaged; a fix file (what the member sends when
asked) stays clean, like a careful new photo. The truth and set.json gain a damage_suite note.
"""

import io
import json
import shutil
import zlib
from collections.abc import Sequence
from pathlib import Path

from PIL import Image

from reimbursement_council.adapters.damage_suite import apply_damage
from reimbursement_council.core.models.claim import Claim

SET_MANIFEST = "set.json"


def read_claims(source: Path) -> list[tuple[Path, Claim]]:
    """Every claim in the set folder, checked against set.json."""
    manifest_path = source / SET_MANIFEST
    if not manifest_path.is_file() or not (source / "reference.json").is_file():
        raise ValueError(f"{source} is not a claim set: it needs set.json and reference.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = sorted(source.glob("*.claim.json"))
    if manifest.get("count") != len(paths):
        raise ValueError(f"{source} has {len(paths)} claims, set.json says {manifest.get('count')}")
    return [(p, Claim.model_validate_json(p.read_text(encoding="utf-8"))) for p in paths]


def _damaged_png(path: Path, kind: str, level: int, strengths: Sequence[float]) -> bytes:
    seed = zlib.crc32(path.name.encode("utf-8"))  # the same file is always damaged the same way
    with Image.open(path) as image:
        damaged = apply_damage(image.convert("RGB"), kind, level, strengths, seed)
    buffer = io.BytesIO()
    damaged.save(buffer, format="PNG")
    return buffer.getvalue()


def write_damaged_set(
    source: Path, out: Path, kind: str, level: int, strengths: Sequence[float]
) -> int:
    """A copy of the set in `out` with every claim document damaged. Returns the claim count."""
    claims = read_claims(source)
    documents = {Path(d.file_path).name for _, claim in claims for d in claim.documents}
    missing = sorted(name for name in documents if not (source / name).is_file())
    if missing:
        raise ValueError(f"{source} is missing documents the claims name: {missing[:5]}")
    out.mkdir(parents=True, exist_ok=False)
    note = {"kind": kind, "level": level}
    manifest = json.loads((source / SET_MANIFEST).read_text(encoding="utf-8"))
    manifest["damage_suite"] = note | {"source": source.name}
    (out / SET_MANIFEST).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    shutil.copyfile(source / "reference.json", out / "reference.json")
    for claim_path, claim in claims:
        shutil.copyfile(claim_path, out / claim_path.name)
        truth_name = claim_path.name.replace(".claim.json", ".truth.json")
        truth = json.loads((source / truth_name).read_text(encoding="utf-8"))
        if truth.get("claim_id") != claim.claim_id:
            raise ValueError(f"{truth_name} is not the truth for {claim.claim_id}")
        truth["damage_suite"] = note
        (out / truth_name).write_text(
            json.dumps(truth, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    for image in sorted(source.glob("*.png")):
        if image.name in documents:
            (out / image.name).write_bytes(_damaged_png(image, kind, level, strengths))
        else:
            shutil.copyfile(image, out / image.name)
    return len(claims)
