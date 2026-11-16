from uuid import UUID

import sqlalchemy as sa

from acciones_ud.brokers.adapters.outbound.identity.broker_directory import SessionFactory
from acciones_ud.identity.adapters.outbound.persistence.tables import users
from acciones_ud.shared.infrastructure.db import unit_of_work


class BrokerRequestReader:
    def __init__(self, sessions: SessionFactory = unit_of_work) -> None:
        self.sessions = sessions

    async def broker_requested(self, investor_id: UUID) -> bool:
        async with self.sessions() as session:
            return bool(
                (
                    await session.execute(
                        sa.select(users.c.broker_requested).where(users.c.id == investor_id)
                    )
                ).scalar_one_or_none()
            )
