"""Shared parts of the check step tests: a fake reader keyed by file bytes, and helpers."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from reimbursement_council.core.models.claim import (
    Document,
    ExtractedField,
    LineItem,
    ReaderOutput,
)
from reimbursement_council.synthetic.claims import member_id

TREATED = (datetime.now(UTC) + timedelta(hours=3) - timedelta(days=2)).date().isoformat()


def field(name: str, value: str, confidence: float = 0.95) -> ExtractedField:
    return ExtractedField(
        document_id="x",
        name=name,
        value=value,
        original_text=value,  # type: ignore[arg-type]
        source="ocr",
        confidence=confidence,
    )


PHARMACY = ReaderOutput(
    fields=[
        field("provider_name", "Green Leaf Pharmacy"),
        field("vat_number", "300765432100003"),
        field("treatment_date", TREATED),
        field("patient_name", "Sara Ahmed"),
        field("subtotal", "1500"),
        field("vat_total", "225"),
        field("total", "1725"),
    ],
    line_items=[
        LineItem(
            description="Paracetamol 500 mg",
            service_code="MED-PARA",
            quantity=1,
            unit_price=1500,
            amount=1500,
            confidence=0.95,
        )
    ],
    qr_payloads=[],
    text_lines=["Green Leaf Pharmacy", "Simplified Tax Invoice", "فاتورة ضريبية مبسطة"],
)
PRESCRIPTION = ReaderOutput(
    fields=[field("patient_name", "Sara Ahmed"), field("treatment_date", TREATED)],
    line_items=[],
    qr_payloads=[],
    text_lines=["Al Noor Clinic", "Prescription", "وصفة طبية", "Paracetamol 500 mg"],
)
UNREADABLE = ReaderOutput(fields=[], line_items=[], qr_payloads=[])
OTHER_PATIENT = PHARMACY.model_copy(
    update={
        "fields": [
            f if f.name != "patient_name" else field("patient_name", "Omar Ahmed")
            for f in PHARMACY.fields
        ]
    }
)
READINGS = {
    b"pharmacy": PHARMACY,
    b"prescription": PRESCRIPTION,
    b"blank": UNREADABLE,
    b"other-patient": OTHER_PATIENT,
}


class FakeReader:
    def read(self, document: Document) -> ReaderOutput:
        data = Path(document.file_path).read_bytes()
        reading = READINGS[data]
        fields = [
            f.model_copy(update={"document_id": document.document_id}) for f in reading.fields
        ]
        return reading.model_copy(update={"fields": fields})


def upload(client: TestClient, *files: tuple[str, bytes]) -> tuple[str, object]:
    response = client.post(
        "/claims",
        data={"patient": member_id(0)},
        files=[("photos", (name, data, "image/png")) for name, data in files],
        follow_redirects=False,
    )
    location = response.headers.get("location", "")
    claim_id = location.split("/claims/")[1].split("/")[0] if location else ""
    return claim_id, response


READ_FORM = {
    "field_provider_name": "Green Leaf Pharmacy",
    "field_vat_number": "300765432100003",
    "field_treatment_date": TREATED,
    "field_patient_name": "Sara Ahmed",
    "field_subtotal": "15.00",
    "field_vat_total": "2.25",
    "field_total": "17.25",
}


def submit(client: TestClient, claim_id: str, **changes: str) -> object:
    return client.post(
        f"/claims/{claim_id}/submit", data=READ_FORM | changes, follow_redirects=False
    )
