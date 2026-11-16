from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.brokers.adapters.outbound.persistence import models as t
from acciones_ud.brokers.adapters.outbound.persistence.repository import Repository
from acciones_ud.brokers.domain.entities import Link
from acciones_ud.brokers.domain.entities import LinkStatus as S
from acciones_ud.brokers.domain.errors import LinkAlreadyExistsError


class LinkRepository(Repository[Link]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, t.links, Link)

    async def insert(self, value: Link) -> bool:
        try:
            return await super().insert(value)
        except IntegrityError as exc:
            original = getattr(exc.orig, "__cause__", None)
            if getattr(original, "constraint_name", None) == "ux_broker_links_open_investor":
                raise LinkAlreadyExistsError() from None
            raise

    async def open_for(self, investor_id: UUID, *, for_update: bool = False) -> Link | None:
        statement = sa.select(t.links).where(
            t.links.c.investor_id == investor_id, t.links.c.status.in_([S.REQUESTED, S.ACTIVE])
        )
        if for_update:
            statement = statement.with_for_update()
        row = (await self.session.execute(statement)).mappings().first()
        return self.record(row) if row is not None else None

    async def page(
        self,
        investor_id: UUID,
        status: S | None,
        start: datetime | None,
        end: datetime | None,
        now: datetime,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[Link], str | None]:
        effective = sa.case(
            (sa.and_(t.links.c.status == S.REQUESTED, t.links.c.expires_at <= now), S.EXPIRED),
            else_=t.links.c.status,
        )
        statement = sa.select(t.links).where(t.links.c.investor_id == investor_id)
        if status:
            statement = statement.where(effective == status)
        if end:
            statement = statement.where(t.links.c.requested_at < end)
        if start:
            last = sa.func.coalesce(
                t.links.c.ended_at,
                sa.case(
                    (
                        t.links.c.status.in_([S.DECLINED, S.CANCELED, S.EXPIRED]),
                        t.links.c.responded_at,
                    ),
                    (effective == S.EXPIRED, t.links.c.expires_at),
                ),
                now,
            )
            statement = statement.where(last >= start)
        return await self.paginated(statement, "requested_at", "id", cursor, limit)
