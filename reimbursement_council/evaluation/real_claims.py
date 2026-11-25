"""Real receipt photos inside a synthetic claim context (real end to end, E1 part 2).

The photo is real (SROIE); the member, policy and submission date are generated, so the right
outcome under our policy is known without hand labels. The policy covers the receipt's dates
(SROIE receipts are from 2017 to 2019), so a claim fails a date rule only if the date is misread.
Pure: no files.
"""

import random
from datetime import UTC, date, datetime, time, timedelta

from reimbursement_council.core.models.claim import Claim, Document
from reimbursement_council.core.models.reference import (
    Member,
    MemberHistory,
    Policy,
    ReferenceData,
)
from reimbursement_council.evaluation.sroie import RealTruth
from reimbursement_council.synthetic.cases import PEOPLE, member_id
from reimbursement_council.synthetic.receipt_content import PATIENTS

REAL_POLICY = "00000000-0000-4000-8000-0000000000c1"
POLICY_START, POLICY_END = date(2015, 1, 1), date(2030, 12, 31)
UNKNOWN_DATE_SUBMISSION = date(2019, 1, 15)  # used when the key's date cannot be parsed


def real_reference() -> ReferenceData:
    people = range(len(PATIENTS))
    return ReferenceData(
        members=[
            Member(
                member_id=member_id(i),
                display_name=PEOPLE[i].en,
                name_ar=PEOPLE[i].ar,
                date_joined=POLICY_START,
                policy_id=REAL_POLICY,
            )
            for i in people
        ],
        policies=[
            Policy(
                policy_id=REAL_POLICY,
                tier="silver",
                start_date=POLICY_START,
                end_date=POLICY_END,
                status="active",
                covered_people=[member_id(i) for i in people],
            )
        ],
        providers=[],  # SROIE shops are not Saudi providers: none can be matched
        histories=[
            MemberHistory(member_id=member_id(i), past_claims=4, past_claims_paid=4, limits_used={})
            for i in people
        ],
    )


def real_claim(seed: int, index: int, image_file: str, truth: RealTruth) -> Claim:
    rng = random.Random(seed * 9_000_011 + index)
    person = member_id(rng.randrange(len(PATIENTS)))
    treated = date.fromisoformat(truth.date) if truth.date else UNKNOWN_DATE_SUBMISSION
    submitted = datetime.combine(treated + timedelta(days=rng.randint(1, 5)), time(9), UTC)
    claim_id = f"real-{seed}-{index:04d}"
    return Claim(
        claim_id=claim_id,
        member_id=person,
        patient_member_id=person,
        policy_id=REAL_POLICY,
        submitted_at=submitted,
        status="submitted",
        documents=[
            Document(
                document_id=f"{claim_id}-doc",
                claim_id=claim_id,
                kind="receipt",
                file_path=image_file,
                image_hash=None,
                uploaded_at=submitted,
            )
        ],
        retries_used=0,
    )
