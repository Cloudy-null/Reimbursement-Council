"""A set of synthetic claims with known right answers. Pure: no drawing, no files.

Each case is a claim with one generated receipt, the prescription or report its services need
(document_sets.py), the defects put into it on purpose, and the ground truth: should we pay,
how much, and which lane a document defect should lead to. All people, clinics and numbers are
made up.
"""

import random
from datetime import UTC, date, datetime, timedelta

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import Claim, Document, ExtractionResult, LineItem
from reimbursement_council.core.models.reference import (
    Member,
    MemberHistory,
    Policy,
    Provider,
    ReferenceData,
)
from reimbursement_council.core.payout import calculate_payout
from reimbursement_council.synthetic.cases import (
    PEOPLE,
    GroundTruth,
    SyntheticCase,
    SyntheticSet,
    member_id,
)
from reimbursement_council.synthetic.document_sets import (
    DOCUMENT_DEFECTS,
    add_documents,
    receipt_options,
)
from reimbursement_council.synthetic.receipt_content import (
    PATIENTS,
    PROVIDERS,
    SAUDI,
    ReceiptContent,
    ReceiptOptions,
    make_receipt_content,
)

__all__ = ["PEOPLE", "GroundTruth", "SyntheticCase", "SyntheticSet", "make_claim_set", "member_id"]

# The defects this generator knows how to make. How often each appears is in
# config/synthetic.yaml (defect_weights), which may name only these.
KNOWN_DEFECTS: tuple[str, ...] = (
    "clean",
    "late",
    "inactive",
    "not_covered",
    "excluded",
    "duplicate",
    "over_limit",
    "overpriced",
    "unlisted",
    "unreadable",
    "tampered_total",
    *DOCUMENT_DEFECTS,
)
DEFECTS = tuple(name for name in KNOWN_DEFECTS if name != "clean")
HARD_RULE_DEFECTS = frozenset({"late", "inactive", "not_covered", "excluded", "duplicate"})

REGULAR = range(len(PATIENTS))
ENDED, LIMIT_USED, OUTSIDER = len(PATIENTS), len(PATIENTS) + 1, len(PATIENTS) + 2
ACTIVE_POLICY = "00000000-0000-4000-8000-0000000000b1"
ENDED_POLICY = "00000000-0000-4000-8000-0000000000b2"


def _reference(rng: random.Random, settings: Settings) -> ReferenceData:
    members = [
        Member(
            member_id=member_id(i),
            display_name=person.en,
            name_ar=person.ar,
            date_joined=date(2023, 1, 1),
            policy_id=ENDED_POLICY if i == ENDED else ACTIVE_POLICY,
        )
        for i, person in enumerate(PEOPLE)
    ]
    policies = [
        Policy(
            policy_id=ACTIVE_POLICY,
            tier="silver",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status="active",
            covered_people=[member_id(i) for i in (*REGULAR, LIMIT_USED)],
        ),
        Policy(
            policy_id=ENDED_POLICY,
            tier="silver",
            start_date=date(2025, 7, 1),
            end_date=date(2026, 6, 30),
            status="active",
            covered_people=[member_id(ENDED)],
        ),
    ]
    providers = [
        Provider(
            provider_id=f"00000000-0000-4000-8000-0000000000e{i}",
            name=p.name_en,
            vat_number=p.vat_number,
            city=p.city_en,
            in_network=True,
            trust_score=0.8,
        )
        for i, p in enumerate(PROVIDERS)
    ]
    histories = []
    for i in REGULAR:
        past = rng.randint(0, 8)
        paid = max(0, past - (1 if rng.random() < 0.2 else 0))
        histories.append(
            MemberHistory(
                member_id=member_id(i), past_claims=past, past_claims_paid=paid, limits_used={}
            )
        )
    tier = settings.policy.tiers["silver"]
    histories.append(
        MemberHistory(
            member_id=member_id(LIMIT_USED),
            past_claims=12,
            past_claims_paid=12,
            limits_used={cat: max(0, limit - 10000) for cat, limit in tier.limits_halalas.items()},
        )
    )
    return ReferenceData(
        members=members, policies=policies, providers=providers, histories=histories
    )


def _correct_payout(
    receipt: ReceiptContent, policy: Policy, history: MemberHistory, settings: Settings
) -> int:
    """Our policy applied to the receipt's true values: the oracle for 'paid right'."""
    from reimbursement_council.core.models.claim import ExtractedField  # local: tiny helper

    vat = ExtractedField(
        document_id="truth",
        name="vat_total",
        value=str(receipt.vat_total),
        original_text="",
        source="qr",
        confidence=1.0,
    )
    items = [
        LineItem(
            description=i.description_en,
            service_code=i.service_code,
            quantity=i.quantity,
            unit_price=i.unit_price,
            amount=i.amount,
            confidence=1.0,
        )
        for i in receipt.items
    ]
    perfect = ExtractionResult(document_id="truth", fields=[vat], line_items=items, checks=[])
    payout = calculate_payout(perfect, policy, history, settings)
    return 0 if payout is None else payout.calculated


def make_claim_set(seed: int, count: int, settings: Settings) -> SyntheticSet:
    reference = _reference(random.Random(seed), settings)
    cases: list[SyntheticCase] = []
    unknown = set(settings.synthetic.defect_weights) - set(KNOWN_DEFECTS)
    if unknown:
        raise ValueError(
            f"synthetic.yaml names defects the generator cannot make: {sorted(unknown)}"
        )
    names, weights = zip(*settings.synthetic.defect_weights.items(), strict=True)
    for index in range(count):
        rng = random.Random(seed * 1_000_003 + index)
        defect = rng.choices(names, weights=weights)[0]
        # A duplicate copies a payable receipt that can be read. An unreadable original leaves
        # nothing to match, so a copy of it is really an honest retake, not a duplicate.
        payable = [
            c
            for c in cases
            if c.truth.should_pay and not c.duplicate_of and c.damage != "unreadable"
        ]
        if defect == "duplicate" and not payable:
            defect = "clean"
        name = f"claim_{seed}_{index:04d}"
        claimant = patient = rng.choice(REGULAR)
        policy_id = ACTIVE_POLICY
        damage = "light" if rng.random() < 0.3 else "none"
        delay_days = rng.randint(95, 130) if defect == "late" else rng.randint(1, 4)
        duplicate_of: str | None = None
        inherited: list[str] = []
        original: SyntheticCase | None = None
        options = ReceiptOptions(with_qr=rng.random() < settings.synthetic.qr_share)
        if defect == "inactive":
            claimant = patient = ENDED
            policy_id = ENDED_POLICY
        elif defect == "not_covered":
            patient = OUTSIDER
        elif defect == "over_limit":
            claimant = patient = LIMIT_USED
        elif defect == "excluded":
            options = options.model_copy(
                update={"provider": PROVIDERS[3], "codes": ["DENT-WHITEN", "DENT-CLEAN"]}
            )
        elif defect == "overpriced":
            options = options.model_copy(update={"price_factor": round(rng.uniform(1.8, 2.6), 2)})
        elif defect == "unlisted":
            options = options.model_copy(update={"unlisted_item": True})
        elif defect == "unreadable":
            damage = "unreadable"
        elif defect == "tampered_total":
            options = options.model_copy(
                update={"printed_total_delta": rng.choice([1000, 2500, 5000])}
            )
        options = receipt_options(defect, rng, options)
        options = options.model_copy(update={"patient": PEOPLE[patient]})
        if defect == "late":
            issued = datetime(2026, 7, 10, 9, 0) + timedelta(days=rng.randrange(0, 20))
            options = options.model_copy(update={"issued_at": issued})

        if defect == "duplicate":
            original = rng.choice(payable)
            receipt = original.receipt
            claimant = next(
                i for i, _ in enumerate(PEOPLE) if member_id(i) == original.claim.member_id
            )
            patient = next(
                i for i, _ in enumerate(PEOPLE) if member_id(i) == original.claim.patient_member_id
            )
            damage = (
                original.damage
                if rng.random() < 0.5
                else ("light" if original.damage == "none" else "none")
            )
            duplicate_of = original.name
            inherited = list(original.truth.defects)
        else:
            receipt = make_receipt_content(rng, settings.prices, options, settings.policy.vat_rate)

        submitted = (receipt.issued_at + timedelta(days=delay_days)).replace(tzinfo=SAUDI)
        if original is not None:
            # Always sent after the original, a few hours to three days later.
            submitted = original.claim.submitted_at.astimezone(SAUDI) + timedelta(
                hours=rng.randint(2, 72)
            )
        claim_id = f"syn-{seed}-{index:04d}"
        claim = Claim(
            claim_id=claim_id,
            member_id=member_id(claimant),
            patient_member_id=member_id(patient),
            policy_id=policy_id,
            submitted_at=submitted.astimezone(UTC),
            status="submitted",
            documents=[
                Document(
                    document_id=f"{claim_id}-doc",
                    claim_id=claim_id,
                    kind="invoice",
                    file_path=f"{name}.png",
                    image_hash=None,
                    uploaded_at=submitted,
                )
            ],
            retries_used=0,
        )
        defects = inherited + ([] if defect == "clean" else [defect])
        should_pay = not (HARD_RULE_DEFECTS & set(defects))
        payout = 0
        if should_pay:
            payout = _correct_payout(
                receipt,
                reference.policy(policy_id),
                reference.history(member_id(patient)),
                settings,
            )
        case = SyntheticCase(
            name=name,
            claim=claim,
            receipt=receipt,
            damage=damage,
            duplicate_of=duplicate_of,
            truth=GroundTruth(should_pay=should_pay, correct_payout=payout, defects=defects),
        )
        cases.append(add_documents(case, defect, seed, index, settings, original))
    return SyntheticSet(seed=seed, reference=reference, cases=cases)
