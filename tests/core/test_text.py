from reimbursement_council.core.text import digits_to_ascii, normalize_text


def test_normalize_english() -> None:
    assert normalize_text("  General   Consultation!! ") == "general consultation"
    assert normalize_text("Chest X-Ray") == "chest x ray"


def test_normalize_arabic_letter_forms() -> None:
    # hamza forms, alef maqsura, taa marbuta, tatweel and diacritics are made the same
    assert normalize_text("أشعة") == normalize_text("اشعه")
    assert normalize_text("الإجمـالي") == normalize_text("الاجمالي")
    assert normalize_text("مُستشفى") == normalize_text("مستشفي")


def test_digits_to_ascii() -> None:
    assert digits_to_ascii("١٧٢٫٥٠") == "172.50"
    assert digits_to_ascii("۱۲۳") == "123"
    assert digits_to_ascii("abc") == "abc"
