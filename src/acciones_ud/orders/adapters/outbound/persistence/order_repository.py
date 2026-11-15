from datetime import datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.orders.adapters.outbound.persistence.tables import events, orders
from acciones_ud.orders.domain.model import Order, OrderEvent
from acciones_ud.orders.domain.pagination import decode, encode
from acciones_ud.shared.infrastructure.entity_repository import EntityRepository


class OrderRepository(EntityRepository[Order]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, orders, Order)

    async def change(self, value: Order, previous: Order, event: OrderEvent) -> bool:
        if not await self.save(value, status=previous.status, fully_filled=previous.fully_filled):
            return False
        await EntityRepository(self.session, events, OrderEvent).insert(event)
        return True

    async def daily_count(self, user_id: UUID, now: datetime) -> int:
        zone = ZoneInfo("America/New_York")
        day = now.astimezone(zone).date()
        start = datetime.combine(day, time.min, zone)
        end = datetime.combine(day + timedelta(days=1), time.min, zone)
        result = await self.session.execute(
            sa.select(sa.func.count())
            .select_from(orders)
            .where(
                orders.c.user_id == user_id, orders.c.created_at >= start, orders.c.created_at < end
            )
        )
        return int(result.scalar_one())

    async def due(self, now: datetime) -> list[Order]:
        result = await self.session.execute(
            sa.select(orders)
            .where(
                orders.c.status.in_(["PENDING", "BROKER_SIGNED"]),
                orders.c.scheduled_for <= now,
                orders.c.returned_for_changes.is_(False),
                orders.c.submit_attempted_at.is_(None),
            )
            .order_by(orders.c.scheduled_for, orders.c.id)
            .limit(100)
            .with_for_update(skip_locked=True)
        )
        return [Order(**row) for row in result.mappings()]

    async def page(
        self,
        user_id: UUID,
        status: str | None,
        symbol: str | None,
        start: datetime | None,
        end: datetime | None,
        page_size: int,
        cursor: str | None,
    ) -> tuple[list[Order], str | None]:
        conditions = [orders.c.user_id == user_id]
        for column, value in ((orders.c.status, status), (orders.c.symbol, symbol)):
            if value is not None:
                conditions.append(column == value)
        if start is not None:
            conditions.append(orders.c.created_at >= start)
        if end is not None:
            conditions.append(orders.c.created_at <= end)
        if cursor:
            at, ident = decode(cursor)
            conditions.append(sa.tuple_(orders.c.created_at, orders.c.id) < (at, ident))
        result = await self.session.execute(
            sa.select(orders)
            .where(*conditions)
            .order_by(orders.c.created_at.desc(), orders.c.id.desc())
            .limit(page_size + 1)
        )
        values = [Order(**row) for row in result.mappings()]
        selected = values[:page_size]
        next_cursor = (
            encode(selected[-1].created_at, selected[-1].id) if len(values) > page_size else None
        )
        return selected, next_cursor
