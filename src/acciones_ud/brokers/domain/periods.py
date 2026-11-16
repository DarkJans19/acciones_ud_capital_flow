from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from acciones_ud.brokers.domain.entities import Link, Period
from acciones_ud.brokers.domain.errors import InvalidPeriodError
from acciones_ud.brokers.domain.link_state_machine import is_terminal


def to_utc_range(period: Period) -> tuple[datetime, datetime]:
    if period.start > period.end:
        raise InvalidPeriodError()
    zone = ZoneInfo("America/New_York")
    try:
        start = datetime.combine(period.start, time.min, zone)
        end = datetime.combine(period.end + timedelta(days=1), time.min, zone)
    except (OverflowError, ValueError):
        raise InvalidPeriodError() from None
    return start.astimezone(UTC), end.astimezone(UTC)


def link_overlaps(link: Link, start: datetime, end: datetime, now: datetime) -> bool:
    terminal = link.responded_at if is_terminal(link.status) else None
    last = link.ended_at or terminal or now
    return link.requested_at < end and last >= start
