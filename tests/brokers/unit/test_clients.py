import pytest

from acciones_ud.brokers.application.client_service import ClientService
from acciones_ud.brokers.application.link_service import LinkService
from acciones_ud.brokers.domain.errors import NotFoundError
from acciones_ud.brokers.domain.ports import OrderFilters
from tests.brokers.support import actors, context


async def test_client_orders_are_gated_before_query_port_and_access_is_lost_on_end():
    ctx = context()
    investor, broker = actors(ctx)
    service, links = ClientService(ctx), LinkService(ctx)
    with pytest.raises(NotFoundError):
        await service.client_orders(broker, investor, OrderFilters())
    assert not ctx.order_query.query_calls
    link = await links.request_link(investor, broker, True)
    await links.accept(broker, link.id)
    assert len(await service.clients(broker)) == 1
    filters = OrderFilters(status="PENDING", symbol="AAPL", page_size=5)
    await service.client_orders(broker, investor, filters)
    assert ctx.order_query.query_calls == [(investor, filters)]
    await links.end_link(investor, link.id, "Ended", True)
    with pytest.raises(NotFoundError):
        await service.client_orders(broker, investor, OrderFilters())
    assert len(ctx.order_query.query_calls) == 1
