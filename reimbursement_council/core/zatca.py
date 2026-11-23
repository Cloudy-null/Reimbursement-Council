"""ZATCA simplified tax invoice QR: base64 of TLV records (tag byte, length byte, UTF-8 value).

Tags 1 to 5: seller name, seller VAT number, timestamp, total with VAT, VAT total.
Later tags (phase 2 hash, signature, key) are skipped.
"""

import base64
import binascii
import logging
from datetime import date
from typing import Self

from pydantic import ValidationError, model_validator

from reimbursement_council.core.models.common import Halalas, Model
from reimbursement_council.core.money import format_sar, parse_sar_to_halalas

logger = logging.getLogger(__name__)

SELLER_NAME, VAT_NUMBER, TIMESTAMP, TOTAL_WITH_VAT, VAT_TOTAL = 1, 2, 3, 4, 5
REQUIRED_TAGS = (SELLER_NAME, VAT_NUMBER, TIMESTAMP, TOTAL_WITH_VAT, VAT_TOTAL)
MAX_VALUE_BYTES = 255


class ZatcaInvoice(Model):
    seller_name: str
    vat_number: str
    timestamp: str
    total_with_vat: Halalas
    vat_total: Halalas

    @model_validator(mode="after")
    def timestamp_starts_with_date(self) -> Self:
        date.fromisoformat(self.timestamp[:10])
        return self


def encode_zatca_tlv(invoice: ZatcaInvoice) -> str:
    values = {
        SELLER_NAME: invoice.seller_name,
        VAT_NUMBER: invoice.vat_number,
        TIMESTAMP: invoice.timestamp,
        TOTAL_WITH_VAT: format_sar(invoice.total_with_vat),
        VAT_TOTAL: format_sar(invoice.vat_total),
    }
    records = bytearray()
    for tag, value in values.items():
        raw = value.encode("utf-8")
        if len(raw) > MAX_VALUE_BYTES:
            raise ValueError(f"ZATCA TLV value for tag {tag} is longer than 255 bytes")
        records += bytes([tag, len(raw)]) + raw
    return base64.b64encode(bytes(records)).decode("ascii")


def _read_records(raw: bytes) -> dict[int, str] | None:
    values: dict[int, str] = {}
    position = 0
    while position < len(raw):
        if position + 2 > len(raw):
            return None
        tag, length = raw[position], raw[position + 1]
        start, end = position + 2, position + 2 + length
        if end > len(raw):
            return None
        if tag in REQUIRED_TAGS:
            try:
                values[tag] = raw[start:end].decode("utf-8")
            except UnicodeDecodeError:
                return None
        position = end
    return values


def decode_zatca_tlv(payload: str) -> ZatcaInvoice | None:
    """The invoice in a QR payload, or None if the payload is not a valid ZATCA invoice."""
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        logger.debug("QR payload is not base64")
        return None
    values = _read_records(raw)
    if values is None or any(tag not in values for tag in REQUIRED_TAGS):
        logger.debug("QR payload is not a complete ZATCA TLV")
        return None
    total = parse_sar_to_halalas(values[TOTAL_WITH_VAT])
    vat = parse_sar_to_halalas(values[VAT_TOTAL])
    if total is None or vat is None:
        logger.debug("QR payload amounts are not money")
        return None
    try:
        return ZatcaInvoice(
            seller_name=values[SELLER_NAME],
            vat_number=values[VAT_NUMBER],
            timestamp=values[TIMESTAMP],
            total_with_vat=total,
            vat_total=vat,
        )
    except ValidationError:
        logger.debug("QR payload timestamp is not a date")
        return None
