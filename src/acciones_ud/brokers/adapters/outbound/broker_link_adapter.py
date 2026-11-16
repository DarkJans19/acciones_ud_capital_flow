from typing import Any, cast
from uuid import UUID

import sqlalchemy as sa

from acciones_ud.brokers.adapters.outbound.identity.broker_directory import SessionFactory
from acciones_ud.brokers.adapters.outbound.persistence.models import links
from acciones_ud.identity.adapters.outbound.persistence import tables as identity
from acciones_ud.shared.domain.clock import Clock, SystemClock
from acciones_ud.shared.infrastructure.db import unit_of_work


class BrokerLinkAdapter:
    """One uncached SQL query per call; shared by MOD-03 and MOD-05 (RFP-04)."""

    def __init__(self, sessions: SessionFactory = unit_of_work, clock: Clock | None = None) -> None:
        self.sessions, self.clock = sessions, clock or SystemClock()

    def query(self, *columns: sa.Column[Any]) -> sa.Select[Any]:
        roles, users = identity.role_assignments, identity.users
        return (
            sa.select(*columns)
            .select_from(
                links.join(roles, roles.c.user_id == links.c.broker_id).join(
                    users, users.c.id == links.c.broker_id
                )
            )
            .where(
                links.c.status == "active",
                roles.c.role_code == "broker",
                identity.effective_assignment(roles, users, self.clock.now()),
            )
        )

    async def is_linked(self, broker_id: UUID, investor_id: UUID) -> bool:
        async with self.sessions() as session:
            row = await session.execute(
                self.query(links.c.id)
                .where(links.c.broker_id == broker_id, links.c.investor_id == investor_id)
                .limit(1)
            )
            return row.first() is not None

    async def linked_investors(self, broker_id: UUID) -> list[UUID]:
        statement = (
            self.query(links.c.investor_id, links.c.started_at)
            .where(links.c.broker_id == broker_id)
            .distinct()
            .order_by(links.c.started_at, links.c.investor_id)
        )
        async with self.sessions() as session:
            rows = await session.execute(statement)
            return [row[0] for row in rows]

    async def reviewing_broker(self, investor_id: UUID) -> UUID | None:
        async with self.sessions() as session:
            value = (
                await session.execute(
                    self.query(links.c.broker_id)
                    .where(
                        links.c.investor_id == investor_id, links.c.order_review_enabled.is_(True)
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            return cast(UUID | None, value)
