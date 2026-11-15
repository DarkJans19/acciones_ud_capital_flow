from decimal import Decimal

from acciones_ud.orders.application.order_reconciler import OrderReconciler
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.domain.errors import OrderSubmissionUnknown
from acciones_ud.orders.domain.model import OrderRequest
from acciones_ud.orders.domain.model import OrderStatus as S
from tests.orders.support import make_context


async def test_timeout_is_resolved_by_lookup_or_two_misses() -> None:
    for found in (True, False):
        ctx, user = make_context()
        ctx.alpaca.outcomes.append(OrderSubmissionUnknown())
        ctx.alpaca.store_on_unknown = found
        service = OrderService(ctx)
        order = await service.create(
            user, OrderRequest("AAPL", "buy", Decimal(1), confirmed=True), "key12345"
        )
        assert order.status == S.SUBMITTED and order.alpaca_order_id is None
        reconciler = OrderReconciler(ctx)
        await reconciler.run_once()
        await reconciler.run_once()
        current = await ctx.uow.work.orders.get(id=order.id)
        reservation = await ctx.uow.work.reservations.get(order_id=order.id)
        assert current.status == (S.SUBMITTED if found else S.FAILED)
        assert reservation.status == ("transferred" if found else "released")
        assert ctx.alpaca.creations[order.client_order_id] == 1


async def test_filled_status_waits_for_activity_and_bracket_legs_are_recorded() -> None:
    ctx, user = make_context()
    service = OrderService(ctx)
    request = OrderRequest(
        "AAPL",
        "buy",
        Decimal(1),
        order_class="bracket",
        confirmed=True,
        take_profit_limit_price=Decimal(12),
        stop_loss_stop_price=Decimal(9),
    )
    order = await service.create(user, request, "key12345")
    raw = ctx.alpaca.orders[("account", order.client_order_id)]
    raw["status"] = "filled"
    raw["legs"] = [
        {"id": "take-profit", "type": "limit", "limit_price": "12", "status": "new"},
        {"id": "stop-loss", "type": "stop", "stop_price": "9", "status": "new"},
    ]
    reconciler = OrderReconciler(ctx)
    await reconciler.run_once()
    current = await ctx.uow.work.orders.get(id=order.id)
    assert current.status == S.EXECUTING and not current.fully_filled and current.filled_qty == 0
    assert not [n for n in ctx.notifier.values if n[1] == "order_executions"]
    ctx.alpaca.fills["account"] = [
        {
            "id": "fill1",
            "order_id": order.alpaca_order_id,
            "qty": "1",
            "price": "10.123456789",
            "transaction_time": ctx.clock.now().isoformat(),
        }
    ]
    await reconciler.run_once()
    await reconciler.run_once()
    current = await ctx.uow.work.orders.get(id=order.id)
    assert current.fully_filled and current.filled_avg_price == Decimal("10.123456789")
    assert len(ctx.uow.work.executions.values) == 1
    assert len([n for n in ctx.notifier.values if n[1] == "order_executions"]) == 1
    assert {leg.alpaca_order_id for leg in ctx.uow.work.legs.values} == {"take-profit", "stop-loss"}
