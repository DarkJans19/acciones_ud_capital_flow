from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.brokers.adapters.outbound.persistence import models as t
from acciones_ud.brokers.adapters.outbound.persistence.repository import Repository
from acciones_ud.brokers.domain.entities import BrokerEvent


class BrokerEventRepository(Repository[BrokerEvent]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, t.events, BrokerEvent)
