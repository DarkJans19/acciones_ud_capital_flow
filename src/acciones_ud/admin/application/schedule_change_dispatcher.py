import logging
from uuid import UUID

from acciones_ud.admin.domain.model import Raw
from acciones_ud.admin.domain.pagination import paginate
from acciones_ud.admin.domain.periods import Period
from acciones_ud.admin.domain.ports import (
    AdminWorkFactory,
    ScheduleChangePort,
    ScheduleNotifierPort,
)
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError

logger = logging.getLogger(__name__)


class ScheduleChangeDispatcher:
    def __init__(
        self,
        uow: AdminWorkFactory,
        orders: ScheduleChangePort,
        notifier: ScheduleNotifierPort,
        clock: Clock,
    ) -> None:
        self.uow, self.orders, self.notifier, self.clock = uow, orders, notifier, clock

    async def dispatch(self, ident: UUID) -> None:
        async with self.uow() as work:
            await work.dispatches.lock(ident)
            if await work.dispatches.get(ident):
                return
            source = await work.dispatches.source(ident)
            if source is None:
                return
            affected = await self.orders.apply(source, self.clock.now())
            recipients = await self.notifier.recipients()
            await work.dispatches.insert(
                {
                    "audit_entry_id": ident,
                    "market_code": source["target_id"],
                    "dispatched_at": self.clock.now(),
                    "affected_orders": affected,
                    "notified_users": len(recipients),
                }
            )
        # At most once attempt: committed marker precedes notifications (D6).
        for recipient in recipients:
            try:
                await self.notifier.notify(
                    recipient,
                    {"change_id": str(ident), "market": source["target_id"], **source["payload"]},
                )
            except Exception:
                logger.warning("Schedule notification failed", extra={"change_id": str(ident)})

    async def run_once(self) -> None:
        async with self.uow() as work:
            ids = await work.dispatches.undispatched()
        for ident in ids:
            try:
                await self.dispatch(ident)
            except (AppError, OSError, TimeoutError):
                logger.warning("Schedule dispatch failed", extra={"change_id": str(ident)})

    async def history(self, market: str, period: Period, cursor: str | None, size: int) -> Raw:
        async with self.uow() as work:
            values = await work.dispatches.history(market, *period.bounds())
        for value in values:
            value.update(value["payload"])
            value["dispatch_status"] = "dispatched" if value["dispatched_at"] else "pending"
        page = paginate(
            values, lambda r: (r["occurred_at"].isoformat(), str(r["id"])), cursor, size
        )
        return {"items": page.items, "next_cursor": page.next_cursor}
