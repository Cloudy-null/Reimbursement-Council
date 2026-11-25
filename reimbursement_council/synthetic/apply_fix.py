"""Act as the member in a self-fix: send the fixed file from the set and try again. Pure.

Used by run-set --simulate-fix to measure self-fix (E8). The claim is changed the way the
website's fix step changes it: the file replaces a document (or is added), retries go up by
one, and a field we asked about once is remembered, so it goes to a person if still wrong.
"""

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from reimbursement_council.core.models.claim import Claim, Document
from reimbursement_council.core.models.decision import SelfFixRequest

ASKED_ONCE = frozenset({"retake_photo", "check_photo", "fix_mismatch"})


def claim_after_fix(
    claim: Claim,
    fix: Mapping[str, Any],
    folder: Path,
    request: SelfFixRequest | None,
    now: datetime,
) -> Claim:
    sent = Document(
        document_id=f"{claim.claim_id}-fix",
        claim_id=claim.claim_id,
        kind=fix["kind"],
        file_path=str(folder / fix["file"]),
        image_hash=None,
        uploaded_at=now,
    )
    kept = [d for d in claim.documents if d.document_id != fix.get("replace")]
    asked = list(claim.retake_fields)
    if request is not None and request.kind in ASKED_ONCE and request.field not in asked:
        asked.append(request.field)
    return claim.model_copy(
        update={
            "documents": [*kept, sent],
            "retries_used": claim.retries_used + 1,
            "retake_fields": asked,
            "edits": [],
        }
    )
