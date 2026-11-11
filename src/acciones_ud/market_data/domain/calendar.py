"""RF-27 / Property 26: calendar range expansion."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from acciones_ud.market_data.domain.entities import (
    CalendarDay,
    CalendarSession,
    Market,
    ScheduleOverride,
)
from acciones_ud.market_data.domain.schedule import resolve
from acciones_ud.shared.domain.errors import AppError, ErrorCode

MAX_RANGE_DAYS = 366


def validate_range(start: date, end: date) -> None:
    if start > end:
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: start")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise AppError(422, ErrorCode.VALIDATION_ERROR, "Invalid field: end")


def expand(
    start: date,
    end: date,
    sessions: list[CalendarSession],
    overrides: list[ScheduleOverride],
    market: Market | None,
    target: ZoneInfo,
) -> list[CalendarDay]:
    validate_range(start, end)
    session_by_day = {session.date: session for session in sessions}
    override_by_day = {override.date: override for override in overrides}
    days: list[CalendarDay] = []
    current = start
    while current <= end:
        days.append(
            resolve(
                current,
                session_by_day.get(current),
                override_by_day.get(current),
                market,
                target,
            )
        )
        current += timedelta(days=1)
    return days
