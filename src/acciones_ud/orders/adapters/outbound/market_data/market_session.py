from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from acciones_ud.market_data.application.calendar import CalendarService
from acciones_ud.orders.domain.model import SessionWindow
from acciones_ud.shared.domain.errors import AppError, ErrorCode


class MarketSessionAdapter:
    def __init__(self, calendar: Callable[[], CalendarService]) -> None:
        self.calendar = calendar

    async def is_open(self, exchange: str, at: datetime) -> bool:
        day = at.astimezone(ZoneInfo("America/New_York")).date()
        view = await self.calendar().calendar(exchange, day, day, None)
        return any(
            entry.open_at is not None
            and entry.close_at is not None
            and entry.open_at <= at < entry.close_at
            for entry in view.days
        )

    async def next_open(self, exchange: str, at: datetime) -> SessionWindow:
        day = at.astimezone(ZoneInfo("America/New_York")).date()
        view = await self.calendar().calendar(exchange, day, day + timedelta(days=365), None)
        for entry in view.days:
            if entry.open_at is not None and entry.close_at is not None and entry.open_at >= at:
                return SessionWindow(entry.open_at, entry.close_at)
        raise AppError(
            409, ErrorCode.MARKET_CLOSED, "No eligible session is available.", {"next_open": None}
        )
