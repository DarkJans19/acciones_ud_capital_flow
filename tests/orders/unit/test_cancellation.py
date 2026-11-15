from decimal import Decimal

import pytest

from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.domain.model import OrderRequest
from acciones_ud.orders.domain.model import OrderStatus as S
from acciones_ud.shared.domain.errors import AppError
from tests.orders.support import make_context


async def test_local_cancel_releases_and_provider_cancel_waits_for_reconciliation() -> None:
    ctx, user = make_context()
    service = OrderService(ctx)
    request = OrderRequest("AAPL", "buy", Decimal(1), confirmed=True, schedule_if_closed=True)
    ctx.sessions.open = False
    local = await service.create(user, request, "key12345")
    canceled, status = await service.cancel(user, local.id, "no_longer_needed", None, True)
    assert status == 200 and canceled.status == S.CANCELED
    assert (await ctx.uow.work.reservations.get(order_id=local.id)).status == "released"
    assert ctx.alpaca.cancel_calls == 0
    with pytest.raises(AppError) as caught:
        await service.cancel(user, local.id, "no_longer_needed", None, True)
    assert caught.value.code == "ORDER_NOT_CANCELLABLE"
    ctx.sessions.open = True
    remote = await service.create(user, request, "key12346")
    unchanged, status = await service.cancel(user, remote.id, "price_changed", None, True)
    assert status == 202 and unchanged.status == S.SUBMITTED
    assert ctx.alpaca.cancel_calls == 1
    with pytest.raises(AppError) as caught:
        await service.cancel(user, remote.id, "other", "", True)
    assert caught.value.status == 422
    detail = await service.get(user, remote.id)
    assert detail["reference_commission_estimated"] is True
    assert detail["reference_commission"] == Decimal("0.20")
    assert len((await service.list(user))["items"]) == 2
