"""The optical claim scenarios (make-optical-claims): what each claim is meant to test.

Prices are fixed per scenario so the right payout is known and can be checked by hand. Pure
data.
"""

from typing import Literal

from reimbursement_council.core.models.common import Halalas, Lane, Model
from reimbursement_council.synthetic.optical_content import PaymentMethod

EyeTest = Literal["invoice", "document", "none"]


class OpticalScenario(Model):
    name: str
    lines: list[tuple[str, Halalas]]
    frames_used: Halalas = 0  # MemberHistory.limits_used["optical_frames"]
    vat_rate: float = 0.0
    payment: PaymentMethod = "mada"
    eye_test: EyeTest = "invoice"
    payment_proof: bool = False
    invoice_number: bool = True
    vat_number: bool = True
    late: bool = False
    defect: str | None = None
    expected_lane: Lane | None = None


FRAME, LENS, EXAM = "OPT-FRAME", "OPT-LENS", "OPT-EXAM"
SCENARIOS: tuple[OpticalScenario, ...] = (
    OpticalScenario(
        name="frames_free_share_under_cap", lines=[(FRAME, 30000), (LENS, 15000)], vat_rate=0.15
    ),
    OpticalScenario(name="frames_free_share_at_cap", lines=[(FRAME, 90000), (LENS, 50000)]),
    OpticalScenario(
        name="frames_partly_used", lines=[(FRAME, 160000), (LENS, 15000)], frames_used=60000
    ),
    OpticalScenario(
        name="frames_partly_used_vat",
        lines=[(FRAME, 120000), (LENS, 40000)],
        frames_used=50000,
        vat_rate=0.15,
    ),
    OpticalScenario(
        name="frames_fully_used", lines=[(FRAME, 80000), (LENS, 30000)], frames_used=100000
    ),
    OpticalScenario(name="lenses_only", lines=[(LENS, 45000)], vat_rate=0.15),
    OpticalScenario(
        name="vat_with_eye_exam_line",
        lines=[(FRAME, 50000), (LENS, 25000), (EXAM, 15000)],
        vat_rate=0.15,
    ),
    OpticalScenario(name="cash_paid", lines=[(FRAME, 40000), (LENS, 20000)], payment="cash"),
    OpticalScenario(
        name="eye_test_separate_document",
        lines=[(FRAME, 60000), (LENS, 30000)],
        eye_test="document",
        vat_rate=0.15,
    ),
    *(
        OpticalScenario(
            name=f"missing_eye_test_{n}",
            lines=[(FRAME, 70000), (LENS, 35000)],
            eye_test="none",
            vat_rate=rate,
            defect="missing_eye_test",
            expected_lane="self_fix",
        )
        for n, rate in ((1, 0.15), (2, 0.0))
    ),
    *(
        OpticalScenario(
            name=f"credit_without_proof_{n}",
            lines=[(FRAME, 55000), (LENS, 25000)],
            payment="credit",
            vat_rate=rate,
            defect="missing_payment_proof",
            expected_lane="self_fix",
        )
        for n, rate in ((1, 0.15), (2, 0.0))
    ),
    OpticalScenario(
        name="credit_with_proof",
        lines=[(FRAME, 55000), (LENS, 25000)],
        payment="credit",
        payment_proof=True,
        vat_rate=0.15,
    ),
    # The real Tabby claim was not held for proof of payment (CHECK in the coordinator).
    OpticalScenario(name="tabby_no_proof", lines=[(FRAME, 75000), (LENS, 35000)], payment="tabby"),
    OpticalScenario(
        name="tabby_no_proof_vat",
        lines=[(FRAME, 45000), (LENS, 30000)],
        payment="tabby",
        vat_rate=0.15,
    ),
    OpticalScenario(
        name="invoice_number_missing",
        lines=[(FRAME, 50000), (LENS, 20000)],
        invoice_number=False,
        defect="invalid_invoice",
        expected_lane="self_fix",
    ),
    OpticalScenario(
        name="vat_number_missing",
        lines=[(FRAME, 50000), (LENS, 20000)],
        vat_number=False,
        vat_rate=0.15,
        defect="invalid_invoice",
        expected_lane="self_fix",
    ),
    *(
        OpticalScenario(
            name=f"late_{n}",
            lines=[(FRAME, 65000), (LENS, 30000)],
            vat_rate=rate,
            late=True,
            defect="late",
            expected_lane="auto_reject",
        )
        for n, rate in ((1, 0.0), (2, 0.15))
    ),
)
