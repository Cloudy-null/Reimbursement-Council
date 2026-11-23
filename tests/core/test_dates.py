from datetime import UTC, date, datetime, timedelta, timezone

from reimbursement_council.core.dates import local_date_from_text, local_date_of, utc_timestamp

RIYADH = 3


def test_local_date_of_moves_late_evening_utc_to_next_day() -> None:
    assert local_date_of(datetime(2026, 11, 20, 22, 0, tzinfo=UTC), RIYADH) == date(2026, 11, 21)
    same_instant = datetime(2026, 11, 21, 1, 0, tzinfo=timezone(timedelta(hours=3)))
    assert local_date_of(same_instant, RIYADH) == date(2026, 11, 21)


def test_local_date_from_text() -> None:
    assert local_date_from_text("2026-08-21T22:30:00Z", RIYADH) == date(2026, 8, 22)
    assert local_date_from_text("2026-08-22T01:30:00", RIYADH) == date(2026, 8, 22)
    assert local_date_from_text("2026-08-22", RIYADH) == date(2026, 8, 22)
    assert local_date_from_text("yesterday", RIYADH) is None


def test_utc_timestamp_normalizes_the_same_instant() -> None:
    expected = "2026-11-15T10:30:00Z"
    assert utc_timestamp("2026-11-15T10:30:00Z", RIYADH) == expected
    assert utc_timestamp("2026-11-15T13:30:00+03:00", RIYADH) == expected
    assert utc_timestamp("2026-11-15 13:30", RIYADH) == expected  # no zone: local time
    assert utc_timestamp("not a time", RIYADH) is None
