from decimal import Decimal
from uuid import uuid4

from acciones_ud.orders.application.order_reconciler import OrderReconciler
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.application.schedule_change import ScheduleChange, ScheduleChangeService
from acciones_ud.orders.domain.errors import OrderSubmissionUnknown
from acciones_ud.orders.domain.model import LinkedAccount, OrderRequest
from acciones_ud.orders.domain.model import OrderStatus as S
from acciones_ud.shared.domain.alpaca_errors import AlpacaUnavailable
from tests.orders.support import make_context


async def test_cancel_with_missing_external_id_is_deferred_then_confirmed() -> None:
    ctx, user = make_context()
    ctx.alpaca.outcomes.append(OrderSubmissionUnknown())
    ctx.alpaca.store_on_unknown = True
    ctx.alpaca.lookup_found = False
    service = OrderService(ctx)
    order = await service.create(
        user, OrderRequest("AAPL", "buy", Decimal(1), confirmed=True), "key12345"
    )
    _, status = await service.cancel(user, order.id, "no_longer_needed", None, True)
    assert status == 202 and ctx.alpaca.cancel_calls == 0
    ctx.alpaca.lookup_found = True
    reconciler = OrderReconciler(ctx)
    await reconciler.run_once()
    await reconciler.run_once()
    assert (await ctx.uow.work.orders.get(id=order.id)).status == S.CANCELED
    assert ctx.uow.work.cancels.values[0].outcome == "applied"


async def test_schedule_resume_cannot_bypass_broker_return() -> None:
    ctx, user = make_context()
    broker = uuid4()
    ctx.brokers.links[user] = broker
    service = OrderService(ctx)
    order = await service.create(
        user, OrderRequest("AAPL", "buy", Decimal(1), confirmed=True), "key12345"
    )
    await service.reviews.return_for_changes(broker, order.id, "Review quantity")
    await ScheduleChangeService(ctx).apply(
        ScheduleChange(uuid4(), "NASDAQ", ctx.clock.now().date(), "Calendar update"),
        ctx.clock.now(),
    )
    resumed = await service.resume(user, order.id)
    assert resumed.status == S.IN_REVIEW and not ctx.alpaca.creations
    approved = await service.reviews.approve(broker, order.id)
    assert approved.status == S.SUBMITTED and not approved.returned_for_changes


async def test_account_failure_does_not_stop_other_accounts() -> None:
    ctx, user = make_context()
    other = uuid4()
    ctx.accounts.values[other] = LinkedAccount(other, "second-account", "ACTIVE")
    service = OrderService(ctx)
    request = OrderRequest("AAPL", "buy", Decimal(1), confirmed=True)
    first = await service.create(user, request, "key12345")
    second = await service.create(other, request, "key12345")
    original = ctx.alpaca.get

    async def get(account_id, order_id):
        if account_id == "account":
            raise AlpacaUnavailable()
        return await original(account_id, order_id)

    ctx.alpaca.get = get
    ctx.alpaca.orders[("second-account", second.client_order_id)]["status"] = "filled"
    ctx.alpaca.fills["second-account"] = [
        {
            "id": "execution",
            "order_id": second.alpaca_order_id,
            "qty": "1",
            "price": "10",
            "transaction_time": ctx.clock.now().isoformat(),
        }
    ]
    await OrderReconciler(ctx).run_once()
    assert (await ctx.uow.work.orders.get(id=first.id)).status == S.SUBMITTED
    assert (await ctx.uow.work.orders.get(id=second.id)).fully_filled
