from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.shared.infrastructure.entity_repository import EntityRepository
from acciones_ud.wallet.adapters.outbound.persistence import tables
from acciones_ud.wallet.domain import model as m
from acciones_ud.wallet.domain.ports import LinkedAccountReader, PremiumFlagWriter, Repository


@dataclass
class WalletWork:
    session: AsyncSession
    accounts: LinkedAccountReader
    premium: PremiumFlagWriter
    banks: Repository[m.BankRelationship]
    transfers: Repository[m.Transfer]
    keys: Repository[m.IdempotencyEntry]
    subscriptions: Repository[m.Subscription]
    payments: Repository[m.Payment]
    events: Repository[m.StripeEvent]
    markers: Repository[m.NotificationMarker]
    cursors: Repository[m.ActivityCursor]

    async def lock_user(self, user_id: UUID) -> None:
        await self.session.execute(
            sa.text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": str(user_id)},
        )


@asynccontextmanager
async def wallet_uow() -> AsyncIterator[WalletWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work
    from acciones_ud.wallet.adapters.outbound.identity.account_reader import IdentityAccountsAdapter
    from acciones_ud.wallet.adapters.outbound.identity.premium_flag_writer import PremiumFlagAdapter

    async with unit_of_work() as session:
        yield WalletWork(
            session,
            IdentityAccountsAdapter(session),
            PremiumFlagAdapter(session),
            EntityRepository(session, tables.banks, m.BankRelationship),
            EntityRepository(session, tables.transfers, m.Transfer),
            EntityRepository(session, tables.keys, m.IdempotencyEntry),
            EntityRepository(session, tables.subscriptions, m.Subscription),
            EntityRepository(session, tables.payments, m.Payment),
            EntityRepository(session, tables.events, m.StripeEvent),
            EntityRepository(session, tables.markers, m.NotificationMarker),
            EntityRepository(session, tables.cursors, m.ActivityCursor),
        )
