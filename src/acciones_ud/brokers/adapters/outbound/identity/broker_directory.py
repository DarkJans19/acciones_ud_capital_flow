from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any, Literal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.brokers.domain.entities import BrokerIdentity
from acciones_ud.brokers.domain.pagination import read_search_cursor
from acciones_ud.identity.adapters.outbound.persistence import tables as t
from acciones_ud.shared.domain.clock import Clock, SystemClock
from acciones_ud.shared.infrastructure.db import unit_of_work

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class BrokerDirectory:
    def __init__(self, sessions: SessionFactory = unit_of_work, clock: Clock | None = None) -> None:
        self.sessions, self.clock = sessions, clock or SystemClock()

    def query(self) -> sa.Select[Any]:
        name = sa.func.concat(t.users.c.first_names, " ", t.users.c.last_names)
        return (
            sa.select(
                t.users.c.id.label("user_id"),
                name.label("name"),
                sa.func.coalesce(t.users.c.firm_name, "").label("firm_name"),
                sa.func.coalesce(t.users.c.license_number, "").label("license_number"),
                sa.func.min(t.role_assignments.c.valid_from).label("broker_since"),
            )
            .join(t.role_assignments, t.role_assignments.c.user_id == t.users.c.id)
            .where(
                t.role_assignments.c.role_code == "broker",
                t.effective_assignment(t.role_assignments, t.users, self.clock.now()),
            )
            .group_by(t.users.c.id)
            .order_by(sa.func.lower(name), t.users.c.id)
        )

    async def get_broker(self, user_id: UUID) -> BrokerIdentity | None:
        async with self.sessions() as session:
            row = (
                (await session.execute(self.query().where(t.users.c.id == user_id)))
                .mappings()
                .first()
            )
        return BrokerIdentity(**row) if row else None

    async def all_active(self, exclude: UUID) -> list[BrokerIdentity]:
        async with self.sessions() as session:
            rows = (await session.execute(self.query().where(t.users.c.id != exclude))).mappings()
            return [BrokerIdentity(**row) for row in rows]

    async def search(
        self, text: str, exclude: UUID, cursor: str | None, limit: int
    ) -> list[BrokerIdentity]:
        name = sa.func.concat(t.users.c.first_names, " ", t.users.c.last_names)
        statement = self.query().where(
            t.users.c.id != exclude,
            sa.or_(
                sa.func.lower(name).contains(text.lower(), autoescape=True),
                sa.func.lower(t.users.c.firm_name).contains(text.lower(), autoescape=True),
            ),
        )
        if cursor:
            statement = statement.where(
                sa.tuple_(sa.func.lower(name), t.users.c.id) > read_search_cursor(cursor)
            )
        async with self.sessions() as session:
            rows = (await session.execute(statement.limit(limit))).mappings()
            return [BrokerIdentity(**row) for row in rows]

    async def has_role(self, user_id: UUID, role: Literal["investor", "broker"]) -> bool:
        async with self.sessions() as session:
            row = await session.execute(
                sa.select(t.users.c.id)
                .join(
                    t.role_assignments,
                    t.role_assignments.c.user_id == t.users.c.id,
                )
                .where(
                    t.users.c.id == user_id,
                    t.role_assignments.c.role_code == role,
                    t.effective_assignment(t.role_assignments, t.users, self.clock.now()),
                )
                .limit(1)
            )
            return row.first() is not None

    async def display_name(self, user_id: UUID) -> str | None:
        async with self.sessions() as session:
            return (
                await session.execute(
                    sa.select(
                        sa.func.concat(t.users.c.first_names, " ", t.users.c.last_names)
                    ).where(t.users.c.id == user_id)
                )
            ).scalar_one_or_none()
