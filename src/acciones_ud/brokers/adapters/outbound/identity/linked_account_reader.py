from uuid import UUID

import sqlalchemy as sa

from acciones_ud.brokers.adapters.outbound.identity.broker_directory import SessionFactory
from acciones_ud.identity.adapters.outbound.persistence.tables import kyc_accounts
from acciones_ud.shared.infrastructure.db import unit_of_work


class LinkedAccountReader:
    def __init__(self, sessions: SessionFactory = unit_of_work) -> None:
        self.sessions = sessions

    async def has_linked_account(self, investor_id: UUID) -> bool:
        async with self.sessions() as session:
            result = await session.execute(
                sa.select(kyc_accounts.c.user_id).where(
                    kyc_accounts.c.user_id == investor_id,
                    kyc_accounts.c.alpaca_account_id.is_not(None),
                )
            )
            return result.first() is not None
