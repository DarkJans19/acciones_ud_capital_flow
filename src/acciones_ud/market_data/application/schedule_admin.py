"""RF-27 / 15.7: default schedules and schedule overrides administration."""

from datetime import date, time
from uuid import UUID

from acciones_ud.market_data.application.calendar import not_found
from acciones_ud.market_data.domain.entities import Market, ScheduleOverride
from acciones_ud.market_data.domain.ports import MarketWorkFactory
from acciones_ud.market_data.domain.schedule import validate_default, validate_override


class ScheduleAdminService:
    def __init__(self, uow: MarketWorkFactory) -> None:
        self.uow = uow

    async def set_default(self, code: str, open_time: time, close_time: time) -> Market:
        validate_default(open_time, close_time)
        async with self.uow() as work:
            market = await work.markets.set_default_schedule(code, open_time, close_time)
            if market is None:
                raise not_found("market")
            return market

    async def clear_default(self, code: str) -> None:
        async with self.uow() as work:
            if not await work.markets.clear_default_schedule(code):
                raise not_found("market")

    async def list_overrides(
        self, code: str, start: date | None, end: date | None
    ) -> list[ScheduleOverride]:
        async with self.uow() as work:
            if await work.markets.market(code) is None:
                raise not_found("market")
            return await work.markets.overrides(code, start, end)

    async def create_override(
        self,
        code: str,
        override_id: UUID,
        day: date,
        closed: bool,
        open_time: time | None,
        close_time: time | None,
    ) -> ScheduleOverride:
        validate_override(closed, open_time, close_time)
        override = ScheduleOverride(
            id=override_id,
            market_code=code,
            date=day,
            closed=closed,
            open_time=open_time,
            close_time=close_time,
        )
        async with self.uow() as work:
            if await work.markets.market(code) is None:
                raise not_found("market")
            return await work.markets.add_override(override)

    async def update_override(
        self,
        code: str,
        override_id: UUID,
        closed: bool,
        open_time: time | None,
        close_time: time | None,
    ) -> ScheduleOverride:
        validate_override(closed, open_time, close_time)
        async with self.uow() as work:
            existing = await work.markets.override(code, override_id)
            if existing is None:
                raise not_found("override")
            updated = ScheduleOverride(
                id=existing.id,
                market_code=existing.market_code,
                date=existing.date,
                closed=closed,
                open_time=open_time,
                close_time=close_time,
            )
            result = await work.markets.update_override(updated)
            if result is None:
                raise not_found("override")
            return result

    async def delete_override(self, code: str, override_id: UUID) -> None:
        async with self.uow() as work:
            if not await work.markets.delete_override(code, override_id):
                raise not_found("override")
