from uuid import UUID


class NullBrokerLink:
    async def reviewing_broker(self, investor_id: UUID) -> UUID | None:
        return None

    async def is_linked(self, broker_id: UUID, investor_id: UUID) -> bool:
        return False

    async def linked_investors(self, broker_id: UUID) -> list[UUID]:
        return []
