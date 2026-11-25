"""Patient names: the same person in another form must match; another person must not."""

import pytest

from reimbursement_council.core.name_match import is_a_name, same_person

RATIO = 0.85


@pytest.mark.parametrize(
    ("read", "account"),
    [
        ("ناصر", "تركي ناصر"),  # a shorter name inside the longer one
        ("Sama Alzanbaqi", "Sama Fayez Reja Alzanbaqi"),
        ("المريض لمى الحربي", "لمى الحربي"),  # a label left in the name
        ("أسماء صالح", "اسماء صالح"),  # Arabic letter forms
        ("لمى حربي", "لمى الحربي"),  # with and without "ال"
        ("Mohammed Saeed", "محمد سعيد"),  # English and Arabic spelling
        ("Khalid Saleh", "خالد صالح"),
        ("Abdullah bin Fahad", "Abdullah Fahad"),
        ("بدرفهد", "بدر فهد"),  # OCR joined the words
    ],
)
def test_the_same_person_matches(read: str, account: str) -> None:
    assert same_person(read, account, RATIO)


@pytest.mark.parametrize(
    ("read", "account"),
    [
        ("محمد سعيد", "راكان الحربي"),
        ("Omar Khalid", "Sara Ahmed"),
        ("Sara Ahmed", "Sara Khalid"),  # same first name, another family
        ("ريم عبد الله", "أسماء الحربي"),
    ],
)
def test_another_person_does_not_match(read: str, account: str) -> None:
    assert not same_person(read, account, RATIO)


def test_a_number_is_not_a_name() -> None:
    assert not is_a_name("311111111100003")
    assert is_a_name("لمى الحربي")
