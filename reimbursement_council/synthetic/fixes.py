"""The fixed version of a fixable defect: the file a member sends when asked. Pure.

- unreadable: a clear photo of the same receipt, replacing the spoiled one.
- missing_prescription, missing_medical_report: the missing document, added.
- patient_name_mismatch, date_mismatch: the same document with the right patient or date,
  replacing the wrong one.
Each plan uses its own random stream, so adding plans never changes a set's claims.
"""

import random
from datetime import timedelta

from reimbursement_council.config.models import Settings
from reimbursement_council.synthetic.cases import FixPlan, SyntheticCase
from reimbursement_council.synthetic.document_content import make_clinical_document
from reimbursement_council.synthetic.document_sets import MISSING_KIND
from reimbursement_council.synthetic.receipt_content import PROVIDERS

MISMATCH_DEFECTS = frozenset({"patient_name_mismatch", "date_mismatch"})
FIXABLE_DEFECTS = frozenset({"unreadable", *MISSING_KIND, *MISMATCH_DEFECTS})


def fix_plan(
    case: SyntheticCase, defect: str, seed: int, index: int, settings: Settings
) -> FixPlan | None:
    if defect not in FIXABLE_DEFECTS or case.duplicate_of is not None:
        return None
    rng = random.Random(seed * 5_000_011 + index)
    receipt = case.receipt
    file_name = f"{case.name}-fix.png"
    if defect == "unreadable":
        return FixPlan(
            file_name=file_name,
            kind="invoice",
            replace_document_id=case.claim.documents[0].document_id,
            clinical=None,
        )
    if defect in MISMATCH_DEFECTS:
        if not case.extra_documents:
            return None
        wrong = case.extra_documents[0]
        right = wrong.content.model_copy(
            update={
                "patient": receipt.patient,
                "issued_at": receipt.issued_at - timedelta(minutes=rng.randint(5, 60)),
            }
        )
        return FixPlan(
            file_name=file_name,
            kind=right.kind,
            replace_document_id=wrong.document_id,
            clinical=right,
        )
    kind = MISSING_KIND[defect]
    provider = receipt.provider
    if provider.kind == "pharmacy":  # the doctor who wrote it works at a clinic
        provider = rng.choice(PROVIDERS[:2])
    services = [
        settings.prices[i.service_code] for i in receipt.items if i.service_code in settings.prices
    ]
    issued = receipt.issued_at - timedelta(minutes=rng.randint(5, 60))
    content = make_clinical_document(rng, kind, provider, receipt.patient, issued, services)
    return FixPlan(file_name=file_name, kind=kind, replace_document_id=None, clinical=content)
