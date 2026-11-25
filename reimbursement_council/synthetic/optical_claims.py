"""An optical claim set with known right answers (make-optical-claims). Pure: no drawing.

Each scenario is one claim for glasses: the frame sub-limit free, partly used or used up, the
member share under or at its cap, an eye test missing, a pay later or credit invoice with or
without proof of payment, a broken invoice, or a late claim. Prices are fixed per scenario so
the payout is known; the seed picks the shop, the people, the dates and the printed numbers.
"""

import random
from datetime import datetime, timedelta

from reimbursement_council.config.models import Settings
from reimbursement_council.core.models.claim import LineItem
from reimbursement_council.core.models.common import DocumentKind
from reimbursement_council.core.models.reference import Provider, ReferenceData
from reimbursement_council.synthetic.cases import GroundTruth, member_id
from reimbursement_council.synthetic.optical_content import (
    SHOPS,
    OpticalInvoice,
    OpticalOptions,
    invoice_sheet,
    make_eye_prescription,
    make_optical_invoice,
)
from reimbursement_council.synthetic.optical_documents import (
    eye_test_sheet,
    make_eye_test,
    make_payment_proof,
    payment_sheet,
)
from reimbursement_council.synthetic.optical_scenarios import SCENARIOS, OpticalScenario
from reimbursement_council.synthetic.printed_sheet import Sheet
from reimbursement_council.synthetic.receipt_content import PROVIDERS, PersonName
from reimbursement_council.synthetic.sheet_cases import (
    SheetCase,
    SheetFix,
    SheetSet,
    made_up_people,
    make_claim,
    missing_groups,
    printed_documents,
    sheet_reference,
    truth_payout,
)

OPTICAL_POLICY = "00000000-0000-4000-8000-0000000000c1"
FIRST_MEMBER = 100  # member ids 100 and up, apart from make-claims people
SHOP_PROVIDERS = [
    Provider(
        provider_id=f"00000000-0000-4000-8000-0000000000f{i}",
        name=shop.name_en,
        vat_number=shop.vat_number,
        city=shop.city_en,
        in_network=True,
        trust_score=0.8,
    )
    for i, shop in enumerate(SHOPS)
]


def _line_items(invoice: OpticalInvoice) -> list[LineItem]:
    return [
        LineItem(
            description=item.name_ar,
            service_code=item.service_code,
            quantity=item.quantity,
            unit_price=item.unit_price,
            amount=item.amount,
            confidence=1.0,
        )
        for item in invoice.items
    ]


def _fix(
    scenario: OpticalScenario,
    name: str,
    invoice_id: str,
    options: OpticalOptions,
    rng: random.Random,
    eye_test: Sheet,
    proof: Sheet,
    settings: Settings,
) -> SheetFix | None:
    """What the member sends when asked: the eye test, the proof of payment, or the shop's
    corrected invoice."""
    file_name = f"{name}-fix.png"
    if scenario.defect == "missing_eye_test":
        return SheetFix(
            file_name=file_name, kind="prescription", replace_document_id=None, sheet=eye_test
        )
    if scenario.defect == "missing_payment_proof":
        return SheetFix(file_name=file_name, kind="receipt", replace_document_id=None, sheet=proof)
    if scenario.defect == "invalid_invoice":
        corrected = options.model_copy(
            update={"with_invoice_number": True, "with_vat_number": True}
        )
        invoice = make_optical_invoice(rng, settings.prices, corrected)
        return SheetFix(
            file_name=file_name,
            kind="invoice",
            replace_document_id=invoice_id,
            sheet=invoice_sheet(invoice),
        )
    return None


def _case(
    seed: int,
    index: int,
    scenario: OpticalScenario,
    person: PersonName,
    reference: ReferenceData,
    settings: Settings,
) -> SheetCase:
    rng = random.Random(seed * 2_000_003 + index)
    if scenario.late:
        issued = datetime(2026, 7, 1, 9, 0) + timedelta(days=rng.randrange(0, 20))
        delay = rng.randint(95, 125)
    else:
        issued = datetime(2026, 9, 1, 9, 0) + timedelta(days=rng.randrange(0, 70))
        delay = rng.randint(1, 10)
    issued += timedelta(minutes=rng.randrange(0, 11 * 60))
    options = OpticalOptions(
        lines=scenario.lines,
        patient=person,
        issued_at=issued,
        vat_rate=scenario.vat_rate,
        payment=scenario.payment,
        with_prescription=scenario.eye_test == "invoice",
        with_invoice_number=scenario.invoice_number,
        with_vat_number=scenario.vat_number,
        shop=SHOPS[index % len(SHOPS)],
    )
    invoice = make_optical_invoice(rng, settings.prices, options)
    eyes = invoice.prescription or make_eye_prescription(rng, person)
    eye_test = eye_test_sheet(make_eye_test(rng, rng.choice(PROVIDERS[:2]), issued, eyes))
    proof = payment_sheet(make_payment_proof(rng, invoice))
    sheets: list[tuple[DocumentKind, Sheet]] = [("invoice", invoice_sheet(invoice))]
    if scenario.eye_test == "document":
        sheets.append(("prescription", eye_test))
    if scenario.payment_proof:
        sheets.append(("receipt", proof))
    name = f"optical_{seed}_{index:04d}"
    claim_id = f"opt-{seed}-{index:04d}"
    documents = printed_documents(claim_id, name, sheets)
    member = member_id(FIRST_MEMBER + index)
    claim = make_claim(claim_id, member, OPTICAL_POLICY, issued + timedelta(days=delay), documents)
    present: set[DocumentKind] = {d.kind for d in documents}
    if scenario.eye_test == "invoice":
        present.add("prescription")  # the eye test printed on the invoice counts
    groups = [list(g) for g in settings.documents.required_by_category["optical"]]
    payout = 0
    if not scenario.late:
        payout = truth_payout(
            _line_items(invoice),
            invoice.vat_total,
            reference.policy(OPTICAL_POLICY),
            reference.history(member),
            settings,
        )
    truth = GroundTruth(
        should_pay=not scenario.late,
        correct_payout=payout,
        defects=[] if scenario.defect is None else [scenario.defect],
        document_kinds={d.document_id: d.kind for d in documents},
        needs_missing=missing_groups(groups, present),
        expected_lane=scenario.expected_lane,
    )
    fix = _fix(scenario, name, documents[0].document_id, options, rng, eye_test, proof, settings)
    return SheetCase(
        name=name,
        scenario=scenario.name,
        claim=claim,
        truth=truth,
        documents=documents,
        fields=invoice.truth(),
        fix=fix,
    )


def make_optical_set(seed: int, settings: Settings) -> SheetSet:
    """One claim per scenario, each for its own made-up member with their own history."""
    people = made_up_people(random.Random(seed), len(SCENARIOS))
    pairs = list(zip(SCENARIOS, people, strict=True))
    ids = [member_id(FIRST_MEMBER + i) for i in range(len(SCENARIOS))]
    used = [{"optical_frames": s.frames_used} if s.frames_used else {} for s in SCENARIOS]
    reference = sheet_reference(OPTICAL_POLICY, ids, people, used, SHOP_PROVIDERS)
    cases = [
        _case(seed, index, scenario, person, reference, settings)
        for index, (scenario, person) in enumerate(pairs)
    ]
    return SheetSet(seed=seed, kind="optical", reference=reference, cases=cases)
