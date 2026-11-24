"""RF-27 / 15.7: default schedules and schedule overrides administration."""

import logging
from dataclasses import asdict
from datetime import date, time
from typing import Protocol
from uuid import UUID
from zoneinfo import ZoneInfo

from acciones_ud.market_data.application.calendar import not_found
from acciones_ud.market_data.domain.entities import Market, ScheduleOverride
from acciones_ud.market_data.domain.ports import MarketWorkFactory
from acciones_ud.market_data.domain.schedule import validate_default, validate_override
from acciones_ud.market_data.domain.schedule_audit import (
    AuditActor,
    ScheduleAuditWriter,
    ScheduleChangeListener,
    build,
)
from acciones_ud.shared.domain.clock import Clock, SystemClock


class AuditedWork(Protocol):
    schedule_audit: ScheduleAuditWriter


class ScheduleAdminService:
    def __init__(
        self,
        uow: MarketWorkFactory,
        actor: AuditActor | None = None,
        listener: ScheduleChangeListener | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.uow = uow
        self.actor, self.listener, self.clock = actor, listener, clock or SystemClock()

    async def _audit(
        self,
        work: object,
        action: str,
        code: str,
        override: UUID | None,
        before: object,
        after: object,
        day: date | None = None,
    ) -> UUID | None:
        if self.actor is None:
            return None
        from typing import cast

        record = build(
            action,
            self.actor,
            code,
            override,
            day or self.clock.now().astimezone(ZoneInfo("America/New_York")).date(),
            before,
            after,
            self.clock.now(),
        )
        writer = cast(AuditedWork, work).schedule_audit
        await writer.append(record)
        return record.id

    def _changed(self, ident: UUID | None) -> None:
        if ident is not None and self.listener:
            try:
                self.listener.changed(ident)
            except Exception:
                logging.getLogger(__name__).warning(
                    "Schedule listener failed", extra={"change_id": str(ident)}
                )

    async def set_default(self, code: str, open_time: time, close_time: time) -> Market:
        validate_default(open_time, close_time)
        async with self.uow() as work:
            before = await work.markets.market(code)
            market = await work.markets.set_default_schedule(code, open_time, close_time)
            if market is None:
                raise not_found("market")
            ident = await self._audit(
                work,
                "market_default_schedule_set",
                code,
                None,
                asdict(before) if before else None,
                asdict(market),
            )
        self._changed(ident)
        return market

    async def clear_default(self, code: str) -> None:
        async with self.uow() as work:
            before = await work.markets.market(code)
            if not await work.markets.clear_default_schedule(code):
                raise not_found("market")
            ident = await self._audit(
                work,
                "market_default_schedule_cleared",
                code,
                None,
                asdict(before) if before else None,
                None,
            )
        self._changed(ident)

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
            result = await work.markets.add_override(override)
            ident = await self._audit(
                work, "schedule_override_created", code, override_id, None, asdict(result), day
            )
        self._changed(ident)
        return result

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
            ident = await self._audit(
                work,
                "schedule_override_updated",
                code,
                override_id,
                asdict(existing),
                asdict(result),
                existing.date,
            )
        self._changed(ident)
        return result

    async def delete_override(self, code: str, override_id: UUID) -> None:
        async with self.uow() as work:
            existing = await work.markets.override(code, override_id)
            if not await work.markets.delete_override(code, override_id):
                raise not_found("override")
            ident = await self._audit(
                work,
                "schedule_override_deleted",
                code,
                override_id,
                asdict(existing) if existing else None,
                None,
                existing.date if existing else None,
            )
        self._changed(ident)
