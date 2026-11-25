"""The shapes of a claim set whose documents are printed sheets (optical, dental), and the
helpers they share: the payout oracle and the claim with its documents. Pure: no drawing.

The files these sets write follow make-claims (cli/claims_set.py), so run-set can score them.
"""

import random
from datetime import UTC, date, datetime

from pydantic import Field

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import (
    Claim,
    Document,
    ExtractedField,
    ExtractionResult,
    LineItem,
)
from reimbursement_council.core.models.common import DocumentKind, Halalas, Model
from reimbursement_council.core.models.reference import (
    Member,
    MemberHistory,
    Policy,
    Provider,
    ReferenceData,
)
from reimbursement_council.core.payout import calculate_payout
from reimbursement_council.synthetic.cases import GroundTruth
from reimbursement_council.synthetic.printed_sheet import Sheet
from reimbursement_council.synthetic.receipt_content import SAUDI, PersonName

SET_LABEL = "real-derived synthetic"  # layouts copied from real documents, all values made up


class PrintedDocument(Model):
    document_id: str
    file_name: str
    kind: DocumentKind
    sheet: Sheet


class SheetFix(Model):
    """The file a member sends when asked: added, or replacing one document."""

    file_name: str
    kind: DocumentKind
    replace_document_id: str | None
    sheet: Sheet


class SheetCase(Model):
    name: str
    scenario: str
    claim: Claim
    truth: GroundTruth
    documents: list[PrintedDocument]  # the invoice first
    # What a perfect reader gets from the invoice (provider, dates, totals, items).
    fields: dict[str, object]
    fix: SheetFix | None = None


class SheetSet(Model):
    seed: int
    label: str = SET_LABEL
    kind: str  # "optical" or "dental"
    reference: ReferenceData
    cases: list[SheetCase] = Field(default_factory=list)


def truth_payout(
    items: list[LineItem],
    vat_total: Halalas,
    policy: Policy,
    history: MemberHistory,
    settings: Settings,
) -> int:
    """Our policy applied to the true values of a bill: the oracle for 'paid right'."""
    vat = ExtractedField(
        document_id="truth",
        name="vat_total",
        value=str(vat_total),
        original_text="",
        source="qr",
        confidence=1.0,
    )
    perfect = ExtractionResult(document_id="truth", fields=[vat], line_items=items, checks=[])
    payout = calculate_payout(perfect, policy, history, settings)
    return 0 if payout is None else payout.calculated


def make_claim(
    claim_id: str,
    member: str,
    policy_id: str,
    submitted: datetime,
    documents: list[PrintedDocument],
) -> Claim:
    """A submitted claim with one Document per printed document. `submitted` is local time."""
    local = submitted.replace(tzinfo=SAUDI)
    return Claim(
        claim_id=claim_id,
        member_id=member,
        patient_member_id=member,
        policy_id=policy_id,
        submitted_at=local.astimezone(UTC),
        status="submitted",
        documents=[
            Document(
                document_id=d.document_id,
                claim_id=claim_id,
                kind=d.kind,
                file_path=d.file_name,
                image_hash=None,
                uploaded_at=local,
            )
            for d in documents
        ],
        retries_used=0,
    )


def missing_groups(
    groups: list[list[DocumentKind]], present: set[DocumentKind]
) -> list[list[DocumentKind]]:
    return [group for group in groups if not present & set(group)]


# Made-up first and family names for the optical and dental sets.
FIRST_NAMES: tuple[tuple[str, str], ...] = (
    ("Maha", "مها"),
    ("Turki", "تركي"),
    ("Asma", "أسماء"),
    ("Bader", "بدر"),
    ("Lama", "لمى"),
    ("Majed", "ماجد"),
    ("Nouf", "نوف"),
    ("Rakan", "راكان"),
)
FAMILY_NAMES: tuple[tuple[str, str], ...] = (
    ("Fahad", "فهد"),
    ("Hamad", "حمد"),
    ("Nasser", "ناصر"),
    ("Saleh", "صالح"),
    ("Al Harbi", "الحربي"),
)


def made_up_people(rng: random.Random, count: int) -> list[PersonName]:
    """`count` different made-up names (at most 40)."""
    pairs = rng.sample([(f, g) for f in FIRST_NAMES for g in FAMILY_NAMES], k=count)
    return [PersonName(en=f"{f[0]} {g[0]}", ar=f"{f[1]} {g[1]}") for f, g in pairs]


def sheet_reference(
    policy_id: str,
    member_ids: list[str],
    people: list[PersonName],
    limits_used: list[dict[str, Halalas]],
    providers: list[Provider],
) -> ReferenceData:
    """One silver policy for 2026 covering every member; each member has their own history."""
    return ReferenceData(
        members=[
            Member(
                member_id=member,
                display_name=person.en,
                name_ar=person.ar,
                date_joined=date(2024, 1, 1),
                policy_id=policy_id,
            )
            for member, person in zip(member_ids, people, strict=True)
        ],
        policies=[
            Policy(
                policy_id=policy_id,
                tier="silver",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                status="active",
                covered_people=member_ids,
            )
        ],
        providers=providers,
        histories=[
            MemberHistory(member_id=member, past_claims=2, past_claims_paid=2, limits_used=used)
            for member, used in zip(member_ids, limits_used, strict=True)
        ],
    )


def printed_documents(
    claim_id: str, name: str, sheets: list[tuple[DocumentKind, Sheet]]
) -> list[PrintedDocument]:
    """The invoice first (file name.png), then the extra documents (name-1.png, ...)."""
    return [
        PrintedDocument(
            document_id=f"{claim_id}-doc{n or ''}",
            file_name=f"{name}-{n}.png" if n else f"{name}.png",
            kind=kind,
            sheet=sheet,
        )
        for n, (kind, sheet) in enumerate(sheets)
    ]
