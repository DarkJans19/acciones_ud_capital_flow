"""RF-27 / Properties 26 and 29: schedule validation and resolution."""

from datetime import date, time
from zoneinfo import ZoneInfo

from acciones_ud.market_data.domain.entities import (
    CalendarDay,
    CalendarSession,
    DayKind,
    Market,
    ScheduleOverride,
)
from acciones_ud.market_data.domain.timezones import market_instant
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def _invalid(field: str, issue: str) -> AppError:
    return AppError(
        422,
        ErrorCode.VALIDATION_ERROR,
        f"Invalid field: {field}",
        {"errors": [{"field": field, "issue": issue}]},
    )


def validate_override(closed: bool, open_time: time | None, close_time: time | None) -> None:
    if closed:
        if open_time is not None or close_time is not None:
            raise _invalid("open_time", "a closed override takes no times")
        return
    if open_time is None:
        raise _invalid("open_time", "required when the market is open")
    if close_time is None:
        raise _invalid("close_time", "required when the market is open")
    if close_time <= open_time:
        raise _invalid("close_time", "must be later than open_time")


def validate_default(open_time: time | None, close_time: time | None) -> None:
    if open_time is None:
        raise _invalid("open_time", "required")
    if close_time is None:
        raise _invalid("close_time", "required")
    if close_time <= open_time:
        raise _invalid("close_time", "must be later than open_time")


def _closed_kind(day: date) -> DayKind:
    return DayKind.WEEKEND if day.weekday() >= 5 else DayKind.HOLIDAY


def resolve(
    day: date,
    session: CalendarSession | None,
    override: ScheduleOverride | None,
    market: Market | None,
    target: ZoneInfo,
) -> CalendarDay:
    if override is not None:
        if override.closed:
            return CalendarDay(date=day, kind=_closed_kind(day), override=True)
        assert override.open_time is not None and override.close_time is not None
        return CalendarDay(
            date=day,
            kind=DayKind.TRADING_DAY,
            open_at=market_instant(day, override.open_time).astimezone(target),
            close_at=market_instant(day, override.close_time).astimezone(target),
            override=True,
        )
    if session is not None:
        open_time = session.open_at
        close_time = session.close_at
        if (
            market is not None
            and market.default_open_time is not None
            and market.default_close_time is not None
        ):
            open_time = market.default_open_time
            close_time = market.default_close_time
        return CalendarDay(
            date=day,
            kind=DayKind.TRADING_DAY,
            open_at=market_instant(day, open_time).astimezone(target),
            close_at=market_instant(day, close_time).astimezone(target),
            override=False,
        )
    return CalendarDay(date=day, kind=_closed_kind(day), override=False)
