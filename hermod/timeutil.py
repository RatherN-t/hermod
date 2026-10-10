"""Datetimes are aware UTC everywhere (SQLModel stores and returns them that way);
patients think in clinic-local time (TIMEZONE)."""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from hermod.config import get_settings


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def utcnow() -> datetime:
    return datetime.now(UTC)


def to_local(dt: datetime) -> datetime:
    return dt.astimezone(local_tz())


def to_utc(dt: datetime) -> datetime:
    """Naive datetimes are taken as clinic-local."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=local_tz())
    return dt.astimezone(UTC)


def fmt_local(dt: datetime) -> str:
    """e.g. 'Sat 10 Oct 08:00'."""
    return to_local(dt).strftime("%a %d %b %H:%M")
