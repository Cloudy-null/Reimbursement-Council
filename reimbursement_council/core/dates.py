"""Dates in local time. Treatment and submission dates are compared as the member sees them.

The offset comes from config/policy.yaml (Saudi Arabia: UTC+3, no daylight saving).
"""

from datetime import UTC, date, datetime, timedelta, timezone


def _zone(offset_hours: int) -> timezone:
    return timezone(timedelta(hours=offset_hours))


def _parse(text: str, offset_hours: int) -> datetime | None:
    """An ISO date or time. Text with no zone is local time."""
    try:
        moment = datetime.fromisoformat(text.strip())
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_zone(offset_hours))
    return moment


def local_date_of(moment: datetime, offset_hours: int) -> date:
    return moment.astimezone(_zone(offset_hours)).date()


def local_date_from_text(text: str, offset_hours: int) -> date | None:
    moment = _parse(text, offset_hours)
    return None if moment is None else local_date_of(moment, offset_hours)


def utc_timestamp(text: str, offset_hours: int) -> str | None:
    """The same instant always gives the same text, for duplicate matching."""
    moment = _parse(text, offset_hours)
    if moment is None:
        return None
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
