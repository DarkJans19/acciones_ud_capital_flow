"""RF-27 / Property 27: time zone conversion preserving the instant."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from acciones_ud.shared.domain.errors import AppError, ErrorCode

DEFAULT_TIMEZONE = "America/New_York"
MARKET_TIMEZONE = ZoneInfo(DEFAULT_TIMEZONE)


def zone(name: str | None) -> ZoneInfo:
    if name is None:
        return ZoneInfo(DEFAULT_TIMEZONE)
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: tz") from None


def iso(instant: datetime, target: ZoneInfo) -> str:
    return instant.astimezone(target).isoformat()


def to_zone(instant: datetime, target: ZoneInfo) -> datetime:
    return instant.astimezone(target)


def market_instant(day: date, moment: time) -> datetime:
    return datetime.combine(day, moment, tzinfo=MARKET_TIMEZONE)
