from reimbursement_council.web.views import field_rows
from tests.factories import make_extraction, make_field


def test_invoice_time_shows_local_time() -> None:
    extraction = make_extraction(
        [
            make_field("invoice_timestamp", "2026-11-20T21:15:00Z", source="qr"),
            make_field("total", "23000", source="qr"),
        ]
    )
    rows = {row.name: row.value for row in field_rows(extraction, 0.9, offset_hours=3)}
    assert rows["invoice_timestamp"] == "2026-11-21 00:15"
    assert rows["total"] == "230.00"
