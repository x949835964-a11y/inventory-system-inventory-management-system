"""Date helpers. Dates are stored as naive UTC and shown in the app's local timezone."""
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    """Current time in UTC without tzinfo (MySQL DATETIME has no timezone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_local(value: datetime | None, tz_name: str = "America/Lima") -> datetime | None:
    """Convert a stored naive-UTC datetime to the given local timezone."""
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(tz_name))


def local_today(tz_name: str = "America/Lima") -> date:
    return datetime.now(ZoneInfo(tz_name)).date()


def local_to_utc(day: date, at: time, tz_name: str = "America/Lima") -> datetime:
    """Local calendar day + local time -> naive UTC (what we store)."""
    return datetime.combine(day, at, tzinfo=ZoneInfo(tz_name)).astimezone(timezone.utc).replace(tzinfo=None)


def local_day_start_utc(day: date, tz_name: str = "America/Lima") -> datetime:
    """UTC instant of local midnight. Lima's 15/10 starts at 05:00 UTC, not at 00:00 UTC."""
    return local_to_utc(day, time.min, tz_name)


def movement_datetime(day: date, tz_name: str = "America/Lima", now: datetime | None = None) -> datetime:
    """Timestamp for a movement dated `day`: the current instant if it is today, local noon otherwise."""
    now = now or utc_now()
    if day == to_local(now, tz_name).date():
        return now
    return local_to_utc(day, time(12, 0), tz_name)
