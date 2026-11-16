from datetime import datetime
from typing import Literal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.brokers.adapters.outbound.persistence import models as t
from acciones_ud.brokers.adapters.outbound.persistence.repository import Repository
from acciones_ud.brokers.domain.entities import Proposal, ProposalMessage
from acciones_ud.brokers.domain.entities import ProposalStatus as S


class ProposalRepository(Repository[Proposal]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, t.proposals, Proposal)

    async def page(
        self,
        user_id: UUID,
        role: Literal["investor", "broker"],
        status: S | None,
        start: datetime | None,
        end: datetime | None,
        now: datetime,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[Proposal], str | None]:
        statement = sa.select(t.proposals).where(t.proposals.c[f"{role}_id"] == user_id)
        if role == "broker":
            statement = statement.where(
                sa.exists(
                    sa.select(t.links.c.id).where(
                        t.links.c.id == t.proposals.c.link_id, t.links.c.status == "active"
                    )
                )
            )
        if status:
            effective = sa.case(
                (
                    sa.and_(t.proposals.c.status == S.SENT, t.proposals.c.expires_at <= now),
                    S.EXPIRED,
                ),
                else_=t.proposals.c.status,
            )
            statement = statement.where(effective == status)
        if start:
            statement = statement.where(t.proposals.c.created_at >= start)
        if end:
            statement = statement.where(t.proposals.c.created_at < end)
        return await self.paginated(statement, "created_at", "id", cursor, limit)


class MessageRepository(Repository[ProposalMessage]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, t.messages, ProposalMessage)

    async def page(
        self, proposal_id: UUID, cursor: str | None, limit: int
    ) -> tuple[list[ProposalMessage], str | None]:
        statement = sa.select(t.messages).where(t.messages.c.proposal_id == proposal_id)
        return await self.paginated(statement, "created_at", "id", cursor, limit, ascending=True)
