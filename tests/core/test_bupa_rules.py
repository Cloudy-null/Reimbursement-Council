"""Document rules from Bupa's claim confirmation FAQ (core day 4b)."""

from reimbursement_council.core.bupa_rules import RuleDocument, eye_prescription_on, rule_requests
from reimbursement_council.core.language import unsupported_language
from tests.factories import repo_settings

CONFIG = repo_settings().documents.bupa_rules
INVOICE = [
    "نور البصر للنظارات فاتورة ضريبية مبسطة",
    "رقم الفاتورة 7900000000001 التاريخ PM 06:35 2026/07/29",
    "الرقم الضريبي 300000000000003",
    "اطار نظارة 1 1,600.00",
]
EYE_TEST = ["EYE SPH CYL Axis ADD", "RIGHT -6.50 -1.50 175 0.00"]


def invoice(lines: list[str], kind: str = "invoice", **flags: bool) -> RuleDocument:
    values = {"has_vat_number": True, "has_line_items": True} | flags
    return RuleDocument(document_id="inv", kind=kind, text_lines=lines, **values)  # type: ignore[arg-type]


def fields(requests: list) -> list[str]:  # type: ignore[type-arg]
    return [r.field for r in requests]


def test_an_eye_test_printed_on_the_invoice_counts() -> None:
    assert eye_prescription_on(invoice(INVOICE + EYE_TEST), CONFIG)
    assert not eye_prescription_on(invoice(INVOICE), CONFIG)


def test_a_valid_invoice_needs_nothing() -> None:
    assert rule_requests([invoice(INVOICE)], ["optical"], "inv", CONFIG) == []


def test_an_invoice_without_number_vat_or_items_asks_for_a_full_tax_invoice() -> None:
    no_number = [line for line in INVOICE if "رقم الفاتورة" not in line]
    for document in (
        invoice(no_number),
        invoice(INVOICE, has_vat_number=False),
        invoice(INVOICE, has_line_items=False),
    ):
        assert fields(rule_requests([document], ["optical"], "inv", CONFIG)) == ["full_tax_invoice"]


def test_dental_needs_a_tooth_number() -> None:
    plain = invoice(INVOICE)
    assert fields(rule_requests([plain], ["dental"], "inv", CONFIG)) == ["tooth_number"]
    with_tooth = invoice([*INVOICE, "حشوة سن رقم السن 14"])
    assert rule_requests([with_tooth], ["dental"], "inv", CONFIG) == []
    english = invoice([*INVOICE, "Filling, Tooth 36"])
    assert rule_requests([english], ["dental"], "inv", CONFIG) == []


def test_a_credit_invoice_needs_a_proof_of_payment() -> None:
    credit = invoice([*INVOICE, "طريقة الدفع آجل"])
    assert fields(rule_requests([credit], ["optical"], "inv", CONFIG)) == ["proof_of_payment"]
    proof = RuleDocument(
        document_id="pay", kind="receipt", text_lines=["Payment received 1,750.00"]
    )
    assert rule_requests([credit, proof], ["optical"], "inv", CONFIG) == []


def test_a_tabby_invoice_is_not_held_for_proof_of_payment() -> None:
    """CHECK in HANDOVER: the real claim paid with Tabby was not held."""
    tabby = invoice([*INVOICE, "تابي 1,750.00"])
    assert rule_requests([tabby], ["optical"], "inv", CONFIG) == []


def test_urdu_and_french_need_a_translation_but_arabic_and_english_do_not() -> None:
    lang = CONFIG.unsupported_language
    assert unsupported_language(["کل رقم 1,750.00 روپے", "رسید ٹیکس"], lang) == "urdu"
    assert unsupported_language(["Facture n 12", "Montant TTC 45,00", "Merci"], lang) == "french"
    assert unsupported_language(INVOICE, lang) is None
    assert unsupported_language(["Invoice No. 12", "Total 45.00", "Date 2026-11-01"], lang) is None
    urdu = RuleDocument(document_id="u", kind="other", text_lines=["کل رقم روپے ٹیکس"])
    found = fields(rule_requests([invoice(INVOICE), urdu], ["optical"], "inv", CONFIG))
    assert found == ["translation"]


def test_rules_can_be_switched_off() -> None:
    off = CONFIG.model_copy(update={"enabled": False})
    assert rule_requests([invoice([])], ["dental"], "inv", off) == []


def test_a_document_without_text_is_not_judged_on_text() -> None:
    blank = invoice([], has_vat_number=False, has_line_items=False)
    assert rule_requests([blank], ["dental"], "inv", CONFIG) == []


def test_an_invoice_number_before_its_arabic_label_counts() -> None:
    lines = [
        "2026/07/29 06:35 PM التاريخ 7900000000001 رقم الفاتورة",
        "الرقم الضريبي 300000000000003",
    ]
    assert rule_requests([invoice(lines)], ["optical"], "inv", CONFIG) == []
