"""RF-27: market calendar, single-day status and clock."""

from dataclasses import dataclass
from datetime import date, datetime

from acciones_ud.market_data.domain.calendar import expand, validate_range
from acciones_ud.market_data.domain.entities import CalendarDay
from acciones_ud.market_data.domain.ports import AlpacaBrokerMarketPort, MarketWorkFactory
from acciones_ud.market_data.domain.schedule import resolve
from acciones_ud.market_data.domain.timezones import to_zone, zone
from acciones_ud.shared.domain.alpaca_errors import AlpacaError, to_app_error
from acciones_ud.shared.domain.errors import AppError, ErrorCode


def not_found(resource: str) -> AppError:
    return AppError(
        404,
        ErrorCode.NOT_FOUND,
        f"{resource.capitalize()} not found.",
        {"resource": resource},
    )


@dataclass(frozen=True)
class CalendarView:
    time_zone: str
    days: list[CalendarDay]


@dataclass(frozen=True)
class StatusView:
    market: str
    day: CalendarDay


class CalendarService:
    def __init__(self, uow: MarketWorkFactory, broker: AlpacaBrokerMarketPort) -> None:
        self.uow = uow
        self.broker = broker

    async def calendar(
        self,
        market_code: str | None,
        start: date,
        end: date,
        tz: str | None,
    ) -> CalendarView:
        target = zone(tz)
        validate_range(start, end)
        async with self.uow() as work:
            market = None
            overrides = []
            if market_code is not None:
                market = await work.markets.market(market_code)
                if market is None:
                    raise not_found("market")
                overrides = await work.markets.overrides(market_code, start, end)
        try:
            sessions = await self.broker.calendar(start, end)
        except AlpacaError as exc:
            raise to_app_error(exc) from None
        return CalendarView(
            time_zone=target.key,
            days=expand(start, end, sessions, overrides, market, target),
        )


class MarketStatusService:
    def __init__(self, uow: MarketWorkFactory, broker: AlpacaBrokerMarketPort) -> None:
        self.uow = uow
        self.broker = broker

    async def status(self, market_code: str, day: date, tz: str | None) -> StatusView:
        target = zone(tz)
        async with self.uow() as work:
            market = await work.markets.market(market_code)
            if market is None:
                raise not_found("market")
            overrides = await work.markets.overrides(market_code, day, day)
        try:
            sessions = await self.broker.calendar(day, day)
        except AlpacaError as exc:
            raise to_app_error(exc) from None
        entry = resolve(
            day,
            next((session for session in sessions if session.date == day), None),
            overrides[0] if overrides else None,
            market,
            target,
        )
        return StatusView(market=market_code, day=entry)


@dataclass(frozen=True)
class ClockView:
    is_open: bool
    next_open: datetime
    next_close: datetime
    timestamp: datetime
    time_zone: str


class ClockService:
    def __init__(self, broker: AlpacaBrokerMarketPort) -> None:
        self.broker = broker

    async def clock(self, tz: str | None) -> ClockView:
        target = zone(tz)
        try:
            value = await self.broker.clock()
        except AlpacaError as exc:
            raise to_app_error(exc) from None
        return ClockView(
            is_open=value.is_open,
            next_open=to_zone(value.next_open, target),
            next_close=to_zone(value.next_close, target),
            timestamp=to_zone(value.timestamp, target),
            time_zone=target.key,
        )
