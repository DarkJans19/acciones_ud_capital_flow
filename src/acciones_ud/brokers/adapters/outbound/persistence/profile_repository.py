from dataclasses import asdict

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.brokers.adapters.outbound.persistence import models as t
from acciones_ud.brokers.adapters.outbound.persistence.repository import Repository
from acciones_ud.brokers.domain.entities import BrokerProfile


class ProfileRepository(Repository[BrokerProfile]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, t.profiles, BrokerProfile)

    async def upsert(self, value: BrokerProfile) -> None:
        statement = insert(t.profiles).values(**asdict(value))
        await self.session.execute(
            statement.on_conflict_do_update(
                index_elements=[t.profiles.c.broker_id],
                set_={key: val for key, val in asdict(value).items() if key != "broker_id"},
            )
        )
