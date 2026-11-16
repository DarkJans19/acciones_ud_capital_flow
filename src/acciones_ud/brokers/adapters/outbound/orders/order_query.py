from uuid import UUID

from acciones_ud.brokers.domain.ports import OrderFilters, OrderQueryPort, ProposalOrderCommand
from acciones_ud.orders.domain.model import Raw


class OrderQuery:
    def __init__(self, port: OrderQueryPort) -> None:
        self.port = port

    async def list_for_investor(self, investor_id: UUID, filters: OrderFilters) -> Raw:
        return await self.port.list_for_investor(investor_id, filters)

    async def find_by_idempotency_key(
        self, investor_id: UUID, key: str, expected: ProposalOrderCommand | None = None
    ) -> UUID | None:
        return await self.port.find_by_idempotency_key(investor_id, key, expected)
