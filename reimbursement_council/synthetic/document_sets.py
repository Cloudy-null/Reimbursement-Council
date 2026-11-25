"""Give a synthetic case the documents its services need, and put in the document defects
(spec 6.6). Pure: no drawing, no files.

Each claim gets the prescription or medical report its benefit categories need. A document
defect takes one away, puts another person or another day on it, or adds a total the member
typed. The documents use their own random stream, so adding them never changes a receipt.
"""

import random
from datetime import timedelta

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import Document, FieldEdit
from reimbursement_council.core.models.common import DocumentKind, Lane
from reimbursement_council.synthetic.cases import PEOPLE, ExtraDocument, SyntheticCase
from reimbursement_council.synthetic.document_content import (
    HEADERS,
    ClinicalKind,
    make_clinical_document,
)
from reimbursement_council.synthetic.receipt_content import (
    PROVIDERS,
    SERVICES_BY_KIND,
    ReceiptContent,
    ReceiptOptions,
)

# The document defects (how often each appears is in config/synthetic.yaml).
DOCUMENT_DEFECTS: tuple[str, ...] = (
    "missing_prescription",
    "missing_medical_report",
    "patient_name_mismatch",
    "date_mismatch",
    "member_edit_supported",
    "member_edit_contradicts",
)
EXPECTED_LANES: dict[str, Lane] = {
    "missing_prescription": "self_fix",
    "missing_medical_report": "self_fix",
    "patient_name_mismatch": "self_fix",
    "date_mismatch": "self_fix",
    "member_edit_contradicts": "human_review",
}
MISSING_KIND: dict[str, ClinicalKind] = {
    "missing_prescription": "prescription",
    "missing_medical_report": "medical_report",
}
CLINIC_VISIT_DEFECTS = frozenset(
    {"missing_medical_report", "patient_name_mismatch", "date_mismatch"}
)
EDIT_DEFECTS = frozenset({"member_edit_supported", "member_edit_contradicts"})
RECEIPT_KIND: DocumentKind = "invoice"  # every receipt layout's title has an invoice word
BILLING: frozenset[DocumentKind] = frozenset({"invoice", "receipt"})
EDIT_EXTRA_HALALAS = 5000  # a contradicting edit types the total 50 SAR higher


def receipt_options(defect: str, rng: random.Random, options: ReceiptOptions) -> ReceiptOptions:
    """The receipt a document defect needs: a pharmacy bill for a missing prescription, a
    clinic visit for the report defects, and a QR code for the edit defects, so the QR can
    judge the typed total."""
    if defect == "missing_prescription":
        return options.model_copy(update={"provider": PROVIDERS[2]})
    if defect in CLINIC_VISIT_DEFECTS:
        rest = [code for code in SERVICES_BY_KIND["clinic"] if code != "CONS-GP"]
        codes = ["CONS-GP", *rng.sample(rest, k=rng.randint(0, 2))]
        return options.model_copy(update={"provider": PROVIDERS[0], "codes": codes})
    if defect in EDIT_DEFECTS:
        return options.model_copy(update={"with_qr": True})
    return options


def required_groups(receipt: ReceiptContent, settings: Settings) -> list[list[DocumentKind]]:
    """The document groups the receipt's services need, read straight from the config."""
    categories = sorted(
        {
            settings.prices[i.service_code].category
            for i in receipt.items
            if i.service_code in settings.prices
        }
    )
    groups: list[list[DocumentKind]] = []
    for category in categories:
        for group in settings.documents.required_by_category.get(category, []):
            if list(group) not in groups:
                groups.append(list(group))
    return groups


def _needed_kinds(groups: list[list[DocumentKind]]) -> list[ClinicalKind]:
    kinds: list[ClinicalKind] = []
    for group in groups:
        clinical = [k for k in group if k in HEADERS]
        if clinical and not BILLING & set(group) and clinical[0] not in kinds:
            kinds.append(clinical[0])
    return kinds


def add_documents(
    case: SyntheticCase,
    defect: str,
    seed: int,
    index: int,
    settings: Settings,
    original: SyntheticCase | None = None,
) -> SyntheticCase:
    """The case with its prescription or report, any document defect, and the truth about
    its documents. A duplicate copies the documents of the claim it copies."""
    rng = random.Random(seed * 7_000_003 + index)
    receipt = case.receipt
    claim = case.claim
    receipt_document = claim.documents[0].model_copy(update={"kind": RECEIPT_KIND})
    groups = required_groups(receipt, settings)
    if original is not None:
        contents = [(d.content, d.damage) for d in original.extra_documents]
    else:
        services = [
            settings.prices[i.service_code]
            for i in receipt.items
            if i.service_code in settings.prices
        ]
        damage = "none" if case.damage == "unreadable" else case.damage
        contents = []
        for kind in _needed_kinds(groups):
            if kind == MISSING_KIND.get(defect):
                continue
            provider = receipt.provider
            if provider.kind == "pharmacy":  # the doctor who wrote it works at a clinic
                provider = rng.choice(PROVIDERS[:2])
            patient = receipt.patient
            if defect == "patient_name_mismatch":
                patient = rng.choice([p for p in PEOPLE if p != receipt.patient])
            issued = receipt.issued_at - timedelta(minutes=rng.randint(5, 60))
            if defect == "date_mismatch":
                issued = receipt.issued_at - timedelta(days=rng.randint(1, 3))
            content = make_clinical_document(rng, kind, provider, patient, issued, services)
            contents.append((content, damage))
    extras = [
        ExtraDocument(
            document_id=f"{claim.claim_id}-doc{n}",
            file_name=f"{case.name}-{n}.png",
            content=content,
            damage=damage,
        )
        for n, (content, damage) in enumerate(contents, start=1)
    ]
    documents = [receipt_document] + [
        Document(
            document_id=e.document_id,
            claim_id=claim.claim_id,
            kind=e.content.kind,
            file_path=e.file_name,
            image_hash=None,
            uploaded_at=receipt_document.uploaded_at,
        )
        for e in extras
    ]
    edits = list(claim.edits)
    if defect in EDIT_DEFECTS:
        extra = EDIT_EXTRA_HALALAS if defect == "member_edit_contradicts" else 0
        edits = [
            FieldEdit(
                document_id=receipt_document.document_id,
                field="total",
                read_value=None,  # the pipeline fills in what the reader really read
                typed_value=str(receipt.total + extra),
            )
        ]
    kinds: dict[str, DocumentKind] = {d.document_id: d.kind for d in documents}
    present = set(kinds.values())
    truth = case.truth.model_copy(
        update={
            "document_kinds": kinds,
            "needs_missing": [g for g in groups if not present & set(g)],
            "expected_lane": EXPECTED_LANES.get(defect),
        }
    )
    return case.model_copy(
        update={
            "claim": claim.model_copy(update={"documents": documents, "edits": edits}),
            "extra_documents": extras,
            "truth": truth,
        }
    )
