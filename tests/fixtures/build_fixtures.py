"""Write the hand-made synthetic fixtures in tests/fixtures/.

Run: uv run python tests/fixtures/build_fixtures.py

Everything here is made up. QR payloads are real ZATCA TLV built with encode_zatca_tlv.
"""

import json
from pathlib import Path
from typing import Any

from reimbursement_council.core.zatca import ZatcaInvoice, encode_zatca_tlv

HERE = Path(__file__).resolve().parent
CLAIMS = HERE / "claims"
SARA = "00000000-0000-4000-8000-0000000000a1"
OMAR = "00000000-0000-4000-8000-0000000000a2"
POLICY = "00000000-0000-4000-8000-0000000000b1"
PROVIDER = "00000000-0000-4000-8000-0000000000e1"
VAT_NUMBER = "300000000000003"
SUBMITTED_AT = "2026-11-20T09:00:00Z"


def field(name: str, value: str, confidence: float = 0.95) -> dict[str, Any]:
    return {
        "name": name,
        "value": value,
        "original_text": value,
        "source": "ocr",
        "confidence": confidence,
    }


def qr(timestamp: str, total: int, vat: int) -> str:
    invoice = ZatcaInvoice(
        seller_name="Al Noor Clinic",
        vat_number=VAT_NUMBER,
        timestamp=timestamp,
        total_with_vat=total,
        vat_total=vat,
    )
    return encode_zatca_tlv(invoice)


def receipt(
    treatment_date: str,
    code: str | None,
    description: str,
    amount: int,
    qr_timestamp: str | None,
    date_confidence: float = 0.95,
) -> dict[str, Any]:
    vat = amount * 15 // 100
    total = amount + vat
    return {
        "fields": [
            field("provider_name", "Al Noor Clinic"),
            field("vat_number", VAT_NUMBER),
            field("treatment_date", treatment_date, date_confidence),
            field("subtotal", str(amount)),
            field("vat_total", str(vat)),
            field("total", str(total)),
            field("patient_name", "Sara Ahmed"),
        ],
        "line_items": [
            {
                "description": description,
                "service_code": code,
                "quantity": 1,
                "unit_price": amount,
                "amount": amount,
                "confidence": 0.95,
            }
        ],
        "qr_payloads": [] if qr_timestamp is None else [qr(qr_timestamp, total, vat)],
    }


READINGS: dict[str, dict[str, Any]] = {
    "clean": receipt(
        "2026-11-15", "CONS-GP", "General consultation", 15000, "2026-11-15T10:30:00Z"
    ),
    "late": receipt("2026-07-01", "CONS-GP", "General consultation", 15000, "2026-07-01T10:30:00Z"),
    # a different day from clean, so the two are not a possible duplicate in a shared store
    "blurry_date": receipt("2026-11-14", "CONS-GP", "General consultation", 15000, None, 0.60),
    "overpriced": receipt(
        "2026-11-16", "CONS-GP", "General consultation", 40000, "2026-11-16T11:00:00Z"
    ),
    "unlisted_service": receipt(
        "2026-11-17", None, "Physio session", 20000, "2026-11-17T09:00:00Z"
    ),
    "prescription": {
        "fields": [field("patient_name", "Sara Ahmed")],
        "line_items": [],
        "qr_payloads": [],
    },
}


def report(treatment_date: str) -> dict[str, Any]:
    """A medical report from the same clinic, for the same patient and day."""
    return {
        "fields": [
            field("patient_name", "Sara Ahmed"),
            field("treatment_date", treatment_date),
            field("provider_name", "Al Noor Clinic"),
        ],
        "line_items": [],
        "qr_payloads": [],
        "text_lines": ["Al Noor Clinic", "Medical Report", "Patient: Sara Ahmed"],
    }


# Outpatient claims need a medical report (config/documents.yaml), so each receipt fixture
# with a consultation gets one from the same day.
for _name, _date in (
    ("clean", "2026-11-15"),
    ("late", "2026-07-01"),
    ("blurry_date", "2026-11-14"),
    ("overpriced", "2026-11-16"),
):
    READINGS[f"report_{_name}"] = report(_date)

# claim file name: (claim number, reading file, document kind, retries used)
CLAIM_FILES: dict[str, tuple[int, str, str, int]] = {
    "clean": (1, "clean", "receipt", 0),
    "late": (2, "late", "receipt", 0),
    "blurry_date": (3, "blurry_date", "receipt", 0),
    # the same claim as blurry_date after two self-fix retries
    "blurry_date_no_retries": (3, "blurry_date", "receipt", 2),
    "overpriced": (5, "overpriced", "receipt", 0),
    "unlisted_service": (6, "unlisted_service", "receipt", 0),
    "prescription_only": (7, "prescription", "prescription", 0),
}


def claim(number: int, reading: str, kind: str, retries: int) -> dict[str, Any]:
    claim_id = f"00000000-0000-4000-8000-0000000000c{number}"
    documents = [
        {
            "document_id": f"00000000-0000-4000-8000-0000000000d{number}",
            "claim_id": claim_id,
            "kind": kind,
            "file_path": f"{reading}.reading.json",
            "image_hash": None,
            "uploaded_at": SUBMITTED_AT,
        }
    ]
    if f"report_{reading}" in READINGS:
        documents.append(
            {
                "document_id": f"00000000-0000-4000-8000-0000000001d{number}",
                "claim_id": claim_id,
                "kind": "medical_report",
                "file_path": f"report_{reading}.reading.json",
                "image_hash": None,
                "uploaded_at": SUBMITTED_AT,
            }
        )
    return {
        "claim_id": claim_id,
        "member_id": SARA,
        "patient_member_id": SARA,
        "policy_id": POLICY,
        "submitted_at": SUBMITTED_AT,
        "status": "submitted",
        "retries_used": retries,
        "documents": documents,
    }


REFERENCE: dict[str, Any] = {
    "members": [
        {
            "member_id": SARA,
            "display_name": "Sara Ahmed",
            "date_joined": "2023-03-01",
            "policy_id": POLICY,
        },
        {
            "member_id": OMAR,
            "display_name": "Omar Ahmed",
            "date_joined": "2026-10-01",
            "policy_id": POLICY,
        },
    ],
    "policies": [
        {
            "policy_id": POLICY,
            "tier": "silver",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "status": "active",
            "covered_people": [SARA, OMAR],
        }
    ],
    "providers": [
        {
            "provider_id": PROVIDER,
            "name": "Al Noor Clinic",
            "vat_number": VAT_NUMBER,
            "city": "Riyadh",
            "in_network": True,
            "trust_score": 0.8,
        }
    ],
    "histories": [{"member_id": SARA, "past_claims": 5, "past_claims_paid": 5, "limits_used": {}}],
}


def write(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def main() -> None:
    CLAIMS.mkdir(parents=True, exist_ok=True)
    write(HERE / "reference.json", REFERENCE)
    for name, reading in READINGS.items():
        write(CLAIMS / f"{name}.reading.json", reading)
    for name, (number, reading_name, kind, retries) in CLAIM_FILES.items():
        write(CLAIMS / f"{name}.claim.json", claim(number, reading_name, kind, retries))


if __name__ == "__main__":
    main()
