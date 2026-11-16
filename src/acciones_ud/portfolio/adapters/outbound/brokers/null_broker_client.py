from uuid import UUID


class NullBrokerClient:
    async def linked_investors(self, broker_id: UUID) -> list[UUID]:
        return []

    async def is_linked(self, broker_id: UUID, investor_id: UUID) -> bool:
        return False
