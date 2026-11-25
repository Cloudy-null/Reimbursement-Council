"""Log masking: personal data never reaches a log line."""

import logging

from reimbursement_council.adapters.log_privacy import MaskingFilter
from reimbursement_council.core.privacy import mask_personal_data


def test_numbers_emails_and_arabic_names_are_masked() -> None:
    text = "VAT 300765432100003, mail sara@example.com, patient سارة أحمد, phone 0551234567"
    masked = mask_personal_data(text)
    assert "300765432100003" not in masked and "0551234567" not in masked
    assert "sara@example.com" not in masked and "سارة" not in masked
    assert masked.count("[number]") == 2 and "[email]" in masked and "[arabic text]" in masked


def test_claim_ids_amounts_and_dates_stay_readable() -> None:
    text = "claim 00000000-0000-4000-8000-000000000001: lane self_fix, total 17250, 2026-11-21"
    assert mask_personal_data(text) == text


def test_the_filter_masks_the_message_and_its_arguments() -> None:
    record = logging.LogRecord(
        "x", logging.INFO, "f", 1, "patient %s vat %s", ("هند", "300000000000003"), None
    )
    assert MaskingFilter().filter(record) is True
    assert record.getMessage() == "patient [arabic text] vat [number]"


def test_saudi_phones_ibans_and_card_numbers_are_masked() -> None:
    text = (
        "call 055 123 4567 or +966 55 123 4567, IBAN SA03 8000 0000 6080 1016 7519, "
        "card 4111-1111-1111-1111"
    )
    masked = mask_personal_data(text)
    assert "123 4567" not in masked and "SA03" not in masked and "4111" not in masked


def test_a_traceback_is_masked_too() -> None:
    try:
        raise ValueError("patient سارة vat 300000000000003")
    except ValueError:
        import sys

        record = logging.LogRecord("x", logging.ERROR, "f", 1, "failed", None, sys.exc_info())
    MaskingFilter().filter(record)
    assert (
        record.exc_text
        and "300000000000003" not in record.exc_text
        and "سارة" not in record.exc_text
    )
