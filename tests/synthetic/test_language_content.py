import random
from datetime import date

import pytest

from reimbursement_council.synthetic.hijri import hijri_text, to_hijri
from reimbursement_council.synthetic.language_content import (
    LANGUAGES,
    SUPPORTED,
    Language,
    make_language_receipt,
)
from tests.factories import repo_settings

READ_ACCURACY_KEYS = {
    "provider_name",
    "vat_number",
    "treatment_date",
    "invoice_time",
    "patient_name",
    "subtotal",
    "vat_total",
    "total",
    "items",
    "has_qr",
    "damage",
    "layout",
}


def test_hijri_dates_match_known_days() -> None:
    assert to_hijri(date(2023, 7, 19)) == (1445, 1, 1)  # 1 Muharram 1445
    assert to_hijri(date(2024, 3, 11)) == (1445, 9, 1)  # 1 Ramadan 1445
    assert hijri_text(date(2026, 11, 25)) == "1448/06/14"


def test_only_french_and_urdu_are_unsupported() -> None:
    assert {name for name, ok in SUPPORTED.items() if not ok} == {"french", "urdu"}


@pytest.mark.parametrize("language", LANGUAGES)
def test_each_language_has_the_truth_read_accuracy_needs(language: Language) -> None:
    settings = repo_settings()
    receipt = make_language_receipt(random.Random(5), language, settings)
    assert receipt == make_language_receipt(random.Random(5), language, settings)
    truth = receipt.truth()
    assert set(truth) >= READ_ACCURACY_KEYS
    assert truth["language"] == truth["layout"] == language
    assert truth["supported"] is SUPPORTED[language]
    assert truth["total"] == str(receipt.content.printed_total)


def _text(language: Language, seed: int = 5) -> str:
    receipt = make_language_receipt(random.Random(seed), language, repo_settings())
    assert receipt.sheet is not None
    return receipt.sheet.text()


def test_the_page_is_in_its_language() -> None:
    assert "Facture" in _text("french") and "Total TTC" in _text("french")
    assert "Ordonnance" in _text("french") and "Montant" in _text("french")
    urdu = _text("urdu")
    assert "رسید" in urdu and "کل رقم" in urdu
    assert any(letter in urdu for letter in "ٹڈڑںے")
    english = _text("english_only")
    assert "Total SAR" in english and not any("؀" <= c <= "ۿ" for c in english)
    arabic = _text("arabic_only")
    assert "الإجمالي" in arabic and not any("a" <= c.lower() <= "z" for c in arabic)


def test_arabic_indic_digits_print_amounts_and_dates_in_eastern_digits() -> None:
    receipt = make_language_receipt(random.Random(5), "arabic_indic_digits", repo_settings())
    assert receipt.sheet is not None
    text = receipt.sheet.text()
    assert not any(c.isascii() and c.isdigit() for c in text)
    assert "٠" in text or "١" in text
    eastern_total = str(receipt.truth()["total"])  # truth stays in western digits
    assert eastern_total.isascii()


def test_hijri_receipts_print_the_hijri_date() -> None:
    for seed in range(4):
        receipt = make_language_receipt(random.Random(seed), "hijri_date", repo_settings())
        assert receipt.sheet is not None and receipt.hijri is not None
        assert f"{receipt.hijri} هـ" in receipt.sheet.text()
        assert receipt.truth()["hijri_date"] == receipt.hijri
        assert receipt.truth()["treatment_date"] == receipt.content.issued_at.date().isoformat()


def test_mixed_uses_the_normal_bilingual_receipt() -> None:
    receipt = make_language_receipt(random.Random(5), "mixed", repo_settings())
    assert receipt.sheet is None
