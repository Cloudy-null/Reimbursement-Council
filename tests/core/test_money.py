import pytest

from reimbursement_council.core.money import apply_rate, format_sar, parse_sar_to_halalas


def test_parse_plain_and_grouped() -> None:
    assert parse_sar_to_halalas("115") == 11500
    assert parse_sar_to_halalas("115.5") == 11550
    assert parse_sar_to_halalas("1,150.50 SAR") == 115050
    assert parse_sar_to_halalas(" 0.05 ") == 5


def test_parse_arabic_indic_digits() -> None:  # Review Focus 1
    assert parse_sar_to_halalas("١٬١٥٠٫٥٠") == 115050
    assert parse_sar_to_halalas("١١٥ ر.س") == 11500
    assert parse_sar_to_halalas("۱۱۵") == 11500
    assert parse_sar_to_halalas("115 ﷼") == 11500


@pytest.mark.parametrize("text", ["", "abc", "12.345", "-5", "1.2.3", "SAR", "1e3", "١٢a"])
def test_parse_rejects_garbage(text: str) -> None:  # Review Focus 1
    assert parse_sar_to_halalas(text) is None


def test_format_sar() -> None:
    assert format_sar(15525) == "155.25"
    assert format_sar(0) == "0.00"
    assert format_sar(5) == "0.05"
    assert format_sar(115050) == "1150.50"


def test_apply_rate_rounds_half_up() -> None:
    assert apply_rate(15, 0.10) == 2  # 1.5 rounds half up
    assert apply_rate(13500, 0.15) == 2025
    assert apply_rate(13500, 0.0) == 0
    assert isinstance(apply_rate(13500, 0.15), int)
