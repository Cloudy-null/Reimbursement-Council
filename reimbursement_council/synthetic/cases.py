"""The shapes of a synthetic claim set, and the made-up people in it. Pure data, no logic.

Kept apart from claims.py so the document set builder can use them without a circular import.
"""

from pydantic import Field

from reimbursement_council.core.models.claim import Claim
from reimbursement_council.core.models.common import DocumentKind, Halalas, Lane, Model
from reimbursement_council.core.models.reference import ReferenceData
from reimbursement_council.synthetic.document_content import ClinicalDocument
from reimbursement_council.synthetic.receipt_content import PATIENTS, PersonName, ReceiptContent

PEOPLE: tuple[PersonName, ...] = (
    *PATIENTS,
    PersonName(en="Hind Saad", ar="هند سعد"),  # on a policy that has ended
    PersonName(en="Fahad Nasser", ar="فهد ناصر"),  # has used almost all benefits
    PersonName(en="Ali Mansour", ar="علي منصور"),  # not covered by the policy
)


def member_id(index: int) -> str:
    return f"00000000-0000-4000-8000-{index:012d}"


class GroundTruth(Model):
    should_pay: bool
    correct_payout: Halalas
    defects: list[str]
    # The true type of every document in the claim, by document id.
    document_kinds: dict[str, DocumentKind] = Field(default_factory=dict)
    # The required document groups the claim does not have (spec 6.1).
    needs_missing: list[list[DocumentKind]] = Field(default_factory=list)
    # The lane a document defect should lead to. None when the defect does not decide it.
    expected_lane: Lane | None = None


class ExtraDocument(Model):
    """A prescription or medical report that goes with the receipt."""

    document_id: str
    file_name: str
    content: ClinicalDocument
    damage: str


class SyntheticCase(Model):
    name: str
    claim: Claim
    receipt: ReceiptContent
    damage: str
    truth: GroundTruth
    duplicate_of: str | None = None
    extra_documents: list[ExtraDocument] = Field(default_factory=list)


class SyntheticSet(Model):
    seed: int
    reference: ReferenceData
    cases: list[SyntheticCase]
