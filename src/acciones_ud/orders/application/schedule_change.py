from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from acciones_ud.orders.application.context import OrderContext, change, is_unsent
from acciones_ud.orders.domain.model import OrderStatus as S
from acciones_ud.orders.domain.model import ScheduleChangeRecord


@dataclass(frozen=True)
class ScheduleChange:
    change_id: UUID
    market_code: str
    effective_from: date
    description: str


@dataclass(frozen=True)
class ScheduleChangeResult:
    affected_order_ids: list[UUID]
    already_applied: bool


class ScheduleChangePort(Protocol):
    async def apply(self, change: ScheduleChange, now: datetime) -> ScheduleChangeResult: ...


class ScheduleChangeService:
    def __init__(self, context: OrderContext) -> None:
        self.ctx = context

    async def apply(self, change_request: ScheduleChange, now: datetime) -> ScheduleChangeResult:
        affected: dict[UUID, list[UUID]] = {}
        async with self.ctx.uow() as work:
            record = ScheduleChangeRecord(
                change_request.change_id, change_request.market_code, now, 0
            )
            if not await work.schedule_changes.insert(record):
                return ScheduleChangeResult([], True)
            candidates = await work.orders.list(exchange=change_request.market_code)
            for user_id in sorted({order.user_id for order in candidates}):
                await work.lock_user(user_id)
                for snapshot in candidates:
                    if snapshot.user_id != user_id:
                        continue
                    order = await work.orders.get(id=snapshot.id)
                    if (
                        order is None
                        or not is_unsent(order)
                        or order.status not in {S.PENDING, S.BROKER_SIGNED, S.HELD}
                    ):
                        continue
                    await change(
                        work,
                        order,
                        S.IN_REVIEW,
                        "schedule_change",
                        now,
                        metadata={
                            "change_id": str(change_request.change_id),
                            "description": change_request.description,
                            "effective_from": change_request.effective_from.isoformat(),
                        },
                    )
                    affected.setdefault(user_id, []).append(order.id)
            await work.schedule_changes.save(
                replace(record, affected_count=sum(len(ids) for ids in affected.values()))
            )
        for ids in affected.values():
            async with self.ctx.uow() as work:
                order = await work.orders.get(id=ids[0])
            if order:
                await self.ctx.notify(
                    order,
                    "schedule_change",
                    order_ids=[str(i) for i in ids],
                    market=change_request.market_code,
                )
        return ScheduleChangeResult([ident for ids in affected.values() for ident in ids], False)
