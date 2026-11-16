from collections.abc import Callable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from acciones_ud.market_data.application.calendar import CalendarService


class SessionReader:
    def __init__(self, calendar: Callable[[], CalendarService]) -> None:
        self.calendar = calendar

    async def last_closed_session(self, at: datetime) -> date | None:
        day = at.astimezone(ZoneInfo("America/New_York")).date()
        view = await self.calendar().calendar(
            "NYSE", day - timedelta(days=365), day, "America/New_York"
        )
        return max(
            (
                entry.date
                for entry in view.days
                if entry.close_at is not None and entry.close_at <= at
            ),
            default=None,
        )
