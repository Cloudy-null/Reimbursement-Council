from reimbursement_council.core.claim_categories import claim_categories
from reimbursement_council.core.document_needs import document_needs
from reimbursement_council.core.models.claim import LineItem
from tests.factories import repo_settings


def item(code: str | None, amount: int = 1000) -> LineItem:
    return LineItem(
        description="x",
        service_code=code,
        quantity=1,
        unit_price=amount,
        amount=amount,
        confidence=0.9,
    )


def test_categories_come_from_matched_items_only() -> None:
    assert claim_categories([item("MED-IBU"), item(None)], repo_settings().prices) == ["pharmacy"]


def test_categories_are_sorted_and_unique() -> None:
    items = [item("LAB-CBC"), item("CONS-GP"), item("LAB-VITD")]
    assert claim_categories(items, repo_settings().prices) == ["lab", "outpatient"]


def test_an_unknown_code_gives_no_category() -> None:
    assert claim_categories([item("NOT-A-CODE")], repo_settings().prices) == []


def test_pharmacy_receipt_without_prescription_needs_one() -> None:
    needs = document_needs(["pharmacy"], ["receipt"], repo_settings())
    assert [(n.group, n.satisfied) for n in needs] == [
        (["invoice", "receipt"], True),
        (["prescription"], False),
    ]
    assert "prescription" in needs[1].request.en.lower()
    assert "وصفة طبية" in needs[1].request.ar


def test_a_group_asks_for_any_of_its_kinds() -> None:
    needs = document_needs(["lab"], [], repo_settings())
    assert needs[0].group == ["invoice", "receipt"] and not needs[0].satisfied
    assert "an invoice or a receipt" in needs[0].request.en


def test_two_categories_need_the_union_once() -> None:
    needs = document_needs(["pharmacy", "outpatient"], ["invoice"], repo_settings())
    assert sorted(tuple(n.group) for n in needs) == [
        ("invoice", "receipt"),
        ("medical_report",),
        ("prescription",),
    ]


def test_no_category_needs_only_a_billing_document() -> None:
    assert [n.group for n in document_needs([], [], repo_settings())] == [["invoice", "receipt"]]
