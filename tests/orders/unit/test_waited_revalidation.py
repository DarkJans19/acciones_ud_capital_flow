from decimal import Decimal

import pytest

from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.domain.model import OrderRequest
from acciones_ud.orders.domain.model import OrderStatus as S
from acciones_ud.shared.domain.errors import AppError
from tests.orders.support import make_context


async def test_failed_waited_validation_is_committed_before_error() -> None:
    ctx, user = make_context()
    ctx.sessions.open = False
    service = OrderService(ctx)
    order = await service.create(
        user,
        OrderRequest("AAPL", "buy", Decimal(1), confirmed=True, schedule_if_closed=True),
        "key12345",
    )
    ctx.sessions.open, ctx.buying_power.value = True, Decimal(0)
    with pytest.raises(AppError) as caught:
        await service.submitter.submit(order.id, waited=True)
    assert caught.value.code == "INSUFFICIENT_BUYING_POWER" and caught.value.status == 409
    assert (await ctx.uow.work.orders.get(id=order.id)).status == S.REJECTED
    assert (await ctx.uow.work.reservations.get(order_id=order.id)).status == "released"
    assert not ctx.alpaca.creations
