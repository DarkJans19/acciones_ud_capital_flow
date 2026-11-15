from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from acciones_ud.orders.adapters.outbound.brokers.null_broker_link import NullBrokerLink
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.domain.model import OrderRequest
from acciones_ud.orders.domain.model import OrderStatus as S
from acciones_ud.shared.domain.errors import AppError
from tests.orders.support import make_context


async def test_broker_return_resubmit_and_approve() -> None:
    ctx, user = make_context()
    broker = uuid4()
    ctx.brokers.links[user] = broker
    service = OrderService(ctx)
    order = await service.create(
        user, OrderRequest("AAPL", "buy", Decimal(1), confirmed=True), "key12345"
    )
    assert order.status == S.IN_REVIEW and not ctx.alpaca.creations
    assert [o.id for o in await service.reviews.queue(broker)] == [order.id]
    assert await service.reviews.queue(uuid4()) == []
    with pytest.raises(AppError) as caught:
        await service.reviews.approve(uuid4(), order.id)
    assert caught.value.code == "ORDER_NOT_FOUND"
    returned = await service.reviews.return_for_changes(broker, order.id, "Adjust quantity")
    assert returned.status == S.PENDING and returned.returned_for_changes
    resubmitted = await service.resubmit(user, order.id, {"qty": Decimal(2)})
    assert resubmitted.status == S.IN_REVIEW and resubmitted.qty == 2
    assert (await ctx.uow.work.reservations.get(order_id=order.id)).amount == Decimal("20.40")
    ctx.sessions.open = False
    signed = await service.reviews.approve(broker, order.id)
    assert signed.status == S.BROKER_SIGNED and signed.scheduled_for
    assert signed.broker_id == broker and signed.broker_signed_at == ctx.clock.now()
    assert not ctx.alpaca.creations
    null_service = OrderService(replace(ctx, brokers=NullBrokerLink()))
    assert await null_service.reviews.queue(broker) == []
