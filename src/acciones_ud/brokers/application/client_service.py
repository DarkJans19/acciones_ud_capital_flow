from uuid import UUID

from acciones_ud.brokers.application.context import BrokerContext
from acciones_ud.brokers.domain.access import require_active_link
from acciones_ud.brokers.domain.entities import LinkStatus
from acciones_ud.brokers.domain.ports import OrderFilters
from acciones_ud.orders.domain.model import Raw


class ClientService:
    def __init__(self, context: BrokerContext) -> None:
        self.ctx = context

    async def clients(self, broker_id: UUID) -> list[Raw]:
        await self.ctx.require_role(broker_id, "broker")
        async with self.ctx.uow() as work:
            links = await work.links.list(broker_id=broker_id, status=LinkStatus.ACTIVE)
            authorizations = {
                link.id: await work.authorizations.get(link_id=link.id, revoked_at=None)
                for link in links
            }
        links.sort(key=lambda link: (link.started_at or link.requested_at, link.investor_id))
        return [
            {
                "investor_id": link.investor_id,
                "name": await self.ctx.directory.display_name(link.investor_id) or "",
                "link_id": link.id,
                "since": link.started_at,
                "trading_authorized": authorizations[link.id] is not None,
                "order_review_enabled": link.order_review_enabled,
            }
            for link in links
        ]

    async def client_orders(self, broker_id: UUID, investor_id: UUID, filters: OrderFilters) -> Raw:
        await self.ctx.require_role(broker_id, "broker")
        async with self.ctx.uow() as work:
            link = await work.links.get(
                broker_id=broker_id, investor_id=investor_id, status=LinkStatus.ACTIVE
            )
        require_active_link(link, await self.ctx.directory.has_role(broker_id, "broker"), "client")
        return await self.ctx.order_query.list_for_investor(investor_id, filters)
