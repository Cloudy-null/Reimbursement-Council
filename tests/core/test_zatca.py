import base64

import pytest

from reimbursement_council.core.zatca import ZatcaInvoice, decode_zatca_tlv, encode_zatca_tlv

INVOICE = ZatcaInvoice(
    seller_name="عيادة النور",
    vat_number="300000000000003",
    timestamp="2026-11-15T10:30:00Z",
    total_with_vat=17250,
    vat_total=2250,
)


def tlv(tag: int, value: str | bytes) -> bytes:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return bytes([tag, len(raw)]) + raw


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def standard_tags(total: str = "172.50") -> list[bytes]:
    return [
        tlv(1, "عيادة النور"),
        tlv(2, "300000000000003"),
        tlv(3, "2026-11-15T10:30:00Z"),
        tlv(4, total),
        tlv(5, "22.50"),
    ]


def test_zatca_round_trip() -> None:
    assert decode_zatca_tlv(encode_zatca_tlv(INVOICE)) == INVOICE


def test_zatca_decodes_hand_built_payload() -> None:
    assert decode_zatca_tlv(b64(b"".join(standard_tags()))) == INVOICE


def test_zatca_ignores_phase_two_tags() -> None:
    extra = [tlv(6, b"\x01\x02hash"), tlv(7, b"signature"), tlv(8, b"key"), tlv(9, b"stamp")]
    assert decode_zatca_tlv(b64(b"".join(standard_tags() + extra))) == INVOICE


def test_encode_rejects_long_values() -> None:
    with pytest.raises(ValueError, match="255"):
        encode_zatca_tlv(INVOICE.model_copy(update={"seller_name": "x" * 256}))


@pytest.mark.parametrize(
    "payload",
    [
        "https://example.com",  # a QR that is a link
        "not base64!!",
        b64(b"\x01\x05abc"),  # truncated: length says 5, only 3 bytes
        b64(b"".join(t for t in standard_tags() if t[0] != 4)),  # tag 4 missing
        b64(b"".join(standard_tags(total="abc"))),  # total is not money
        b64(tlv(1, b"\xff\xfe") + b"".join(standard_tags()[1:])),  # bad UTF-8
        b64(b"".join(standard_tags()[:2]) + tlv(3, "yesterday") + b"".join(standard_tags()[3:])),
        "",
    ],
)
def test_zatca_rejects_non_zatca_payloads(payload: str) -> None:  # Review Focus 2
    assert decode_zatca_tlv(payload) is None
