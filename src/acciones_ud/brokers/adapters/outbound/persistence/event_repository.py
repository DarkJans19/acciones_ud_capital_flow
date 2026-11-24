from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.brokers.adapters.outbound.persistence import models as t
from acciones_ud.brokers.adapters.outbound.persistence.repository import Repository
from acciones_ud.brokers.domain.entities import BrokerEvent


class BrokerEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._rows = Repository(session, t.events, BrokerEvent)

    async def get(self, *, for_update: bool = False, **filters: object) -> BrokerEvent | None:
        return await self._rows.get(for_update=for_update, **filters)

    async def list(self, **filters: object) -> list[BrokerEvent]:
        return await self._rows.list(**filters)

    async def insert(self, value: BrokerEvent) -> bool:
        return await self._rows.insert(value)
