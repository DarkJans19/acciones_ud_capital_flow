from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.brokers.adapters.outbound.persistence import models as t
from acciones_ud.brokers.adapters.outbound.persistence.event_repository import BrokerEventRepository
from acciones_ud.brokers.adapters.outbound.persistence.link_repository import LinkRepository
from acciones_ud.brokers.adapters.outbound.persistence.profile_repository import ProfileRepository
from acciones_ud.brokers.adapters.outbound.persistence.proposal_repository import (
    MessageRepository,
    ProposalRepository,
)
from acciones_ud.brokers.adapters.outbound.persistence.rating_repository import RatingRepository
from acciones_ud.brokers.adapters.outbound.persistence.repository import Repository
from acciones_ud.brokers.domain import entities as e
from acciones_ud.brokers.domain import ports as p
from acciones_ud.brokers.domain.ports import BrokerWork


@dataclass
class SqlBrokerWork:
    session: AsyncSession
    links: p.LinkRepository
    authorizations: p.Repository[e.TradingAuthorization]
    proposals: p.ProposalRepository
    versions: p.Repository[e.ProposalVersion]
    decisions: p.Repository[e.ProposalDecision]
    messages: p.MessageRepository
    ratings: p.RatingRepository
    profiles: p.ProfileRepository
    events: p.Repository[e.BrokerEvent]

    async def lock_investor(self, investor_id: UUID) -> None:
        await self.session.execute(
            sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"broker-link:{investor_id}"},
        )


def build_work(session: AsyncSession) -> SqlBrokerWork:
    return SqlBrokerWork(
        session,
        LinkRepository(session),
        Repository(session, t.authorizations, e.TradingAuthorization),
        ProposalRepository(session),
        Repository(session, t.versions, e.ProposalVersion),
        Repository(session, t.decisions, e.ProposalDecision),
        MessageRepository(session),
        RatingRepository(session),
        ProfileRepository(session),
        BrokerEventRepository(session),
    )


@asynccontextmanager
async def broker_uow() -> AsyncIterator[BrokerWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:
        yield build_work(session)
