"""HTTP contracts for markets, calendar and schedules (RF-27)."""

from datetime import date, datetime, time

from pydantic import BaseModel, StrictBool

from acciones_ud.market_data.application.calendar import CalendarView, ClockView, StatusView
from acciones_ud.market_data.domain.entities import CalendarDay, ScheduleOverride


class CalendarDayOut(BaseModel):
    date: date
    kind: str
    open_at: datetime | None
    close_at: datetime | None
    override: bool

    @classmethod
    def of(cls, day: CalendarDay) -> "CalendarDayOut":
        return cls(
            date=day.date,
            kind=day.kind.value,
            open_at=day.open_at,
            close_at=day.close_at,
            override=day.override,
        )


class CalendarOut(BaseModel):
    time_zone: str
    days: list[CalendarDayOut]

    @classmethod
    def of(cls, view: CalendarView) -> "CalendarOut":
        return cls(
            time_zone=view.time_zone,
            days=[CalendarDayOut.of(day) for day in view.days],
        )


class ClockOut(BaseModel):
    is_open: bool
    next_open: datetime
    next_close: datetime
    timestamp: datetime
    time_zone: str

    @classmethod
    def of(cls, view: ClockView) -> "ClockOut":
        return cls(
            is_open=view.is_open,
            next_open=view.next_open,
            next_close=view.next_close,
            timestamp=view.timestamp,
            time_zone=view.time_zone,
        )


class MarketStatusOut(BaseModel):
    market: str
    date: date
    open: bool
    open_at: datetime | None
    close_at: datetime | None
    override: bool

    @classmethod
    def of(cls, view: StatusView) -> "MarketStatusOut":
        return cls(
            market=view.market,
            date=view.day.date,
            open=view.day.kind.value == "trading_day",
            open_at=view.day.open_at,
            close_at=view.day.close_at,
            override=view.day.override,
        )


class DefaultScheduleIn(BaseModel):
    open_time: time
    close_time: time


class DefaultScheduleOut(BaseModel):
    market: str
    open_time: time
    close_time: time


class ScheduleOverrideIn(BaseModel):
    date: date
    closed: StrictBool
    open_time: time | None = None
    close_time: time | None = None


class ScheduleOverrideUpdateIn(BaseModel):
    closed: StrictBool
    open_time: time | None = None
    close_time: time | None = None


class ScheduleOverrideOut(BaseModel):
    id: str
    market: str
    date: date
    closed: bool
    open_time: time | None
    close_time: time | None

    @classmethod
    def of(cls, override: ScheduleOverride) -> "ScheduleOverrideOut":
        return cls(
            id=str(override.id),
            market=override.market_code,
            date=override.date,
            closed=override.closed,
            open_time=override.open_time,
            close_time=override.close_time,
        )
