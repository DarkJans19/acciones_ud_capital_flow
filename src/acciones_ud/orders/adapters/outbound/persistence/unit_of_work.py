from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.orders.adapters.outbound.persistence import tables as t
from acciones_ud.orders.adapters.outbound.persistence.order_repository import OrderRepository
from acciones_ud.orders.domain import model as m
from acciones_ud.orders.domain.ports import OrderRepository as OrderRepositoryPort
from acciones_ud.orders.domain.ports import Repository
from acciones_ud.shared.infrastructure.entity_repository import EntityRepository


@dataclass
class OrderWork:
    session: AsyncSession
    orders: OrderRepositoryPort
    legs: Repository[m.OrderLeg]
    events: Repository[m.OrderEvent]
    executions: Repository[m.Execution]
    reservations: Repository[m.Reservation]
    reauthorizations: Repository[m.ReauthorizationRequest]
    cancels: Repository[m.CancelRequest]
    comments: Repository[m.ReviewComment]
    keys: Repository[m.IdempotencyEntry]
    schedule_changes: Repository[m.ScheduleChangeRecord]
    cursors: Repository[m.ActivityCursor]

    async def lock_user(self, user_id: UUID) -> None:
        await self.session.execute(
            sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": str(user_id)},
        )


def build_work(session: AsyncSession) -> OrderWork:
    return OrderWork(
        session,
        OrderRepository(session),
        EntityRepository(session, t.legs, m.OrderLeg),
        EntityRepository(session, t.events, m.OrderEvent),
        EntityRepository(session, t.executions, m.Execution),
        EntityRepository(session, t.reservations, m.Reservation),
        EntityRepository(session, t.reauthorizations, m.ReauthorizationRequest),
        EntityRepository(session, t.cancels, m.CancelRequest),
        EntityRepository(session, t.comments, m.ReviewComment),
        EntityRepository(session, t.keys, m.IdempotencyEntry),
        EntityRepository(session, t.schedule_changes, m.ScheduleChangeRecord),
        EntityRepository(session, t.cursors, m.ActivityCursor),
    )


@asynccontextmanager
async def order_uow() -> AsyncIterator[OrderWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:
        yield build_work(session)
