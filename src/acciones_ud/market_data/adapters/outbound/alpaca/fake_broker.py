"""Deterministic Alpaca Broker market double. Tests never reach the network."""

from datetime import date, datetime, time
from typing import Any

from acciones_ud.market_data.domain.entities import (
    CalendarSession,
    Instrument,
    MarketClock,
)


def _default_clock() -> MarketClock:
    return MarketClock(
        is_open=True,
        next_open=datetime.fromisoformat("2024-01-02T09:30:00-05:00"),
        next_close=datetime.fromisoformat("2024-01-02T16:00:00-05:00"),
        timestamp=datetime.fromisoformat("2024-01-02T10:00:00-05:00"),
    )


class FakeAlpacaBrokerMarket:
    def __init__(self) -> None:
        self.assets: list[Instrument] = []
        self.asset: Instrument | None = None
        self.sessions: list[CalendarSession] = []
        self.clock_value: MarketClock = _default_clock()
        self.errors: dict[str, list[Exception | None]] = {}
        self.calls: list[str] = []

    def fail(self, method: str, error: Exception, times: int = 1) -> None:
        self.errors.setdefault(method, []).extend([error] * times)

    def _raise_scripted(self, method: str) -> None:
        self.calls.append(method)
        queue = self.errors.get(method)
        if queue:
            error = queue.pop(0)
            if error is not None:
                raise error

    async def list_assets(self) -> list[Instrument]:
        self._raise_scripted("list_assets")
        return list(self.assets)

    async def get_asset(self, symbol: str) -> Instrument:
        self._raise_scripted("get_asset")
        if self.asset is None:
            raise AssertionError("FakeAlpacaBrokerMarket.asset was not configured")
        return self.asset

    async def calendar(self, start: date, end: date) -> list[CalendarSession]:
        self._raise_scripted("calendar")
        return [
            session
            for session in self.sessions
            if start <= session.date <= end
        ]

    async def clock(self) -> MarketClock:
        self._raise_scripted("clock")
        return self.clock_value


def calendar_session(day: str, open_at: str = "09:30", close_at: str = "16:00") -> CalendarSession:
    return CalendarSession(
        date=date.fromisoformat(day),
        open_at=time.fromisoformat(open_at),
        close_at=time.fromisoformat(close_at),
    )


def instrument(
    symbol: str,
    *,
    name: str | None = None,
    exchange: str = "NASDAQ",
    tradable: bool = True,
    sector: str | None = None,
    status: str = "active",
    **extra: Any,
) -> Instrument:
    return Instrument(
        symbol=symbol,
        name=name or f"{symbol} Incorporated",
        exchange=exchange,
        tradable=tradable,
        sector=sector,
        status=status,
        **extra,
    )
