from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.orders.application.order_reconciler import OrderReconciler
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.domain.model import OrderRequest
from acciones_ud.shared.domain.errors import AppError
from tests.orders.support import make_context


# Feature: orders-mod-03, Property 10: Ejecuciones idempotentes y acotadas
@settings(max_examples=100)
@given(
    st.integers(1, 30),
    st.lists(st.tuples(st.integers(1, 12), st.integers(1, 20000)), min_size=5, max_size=5),
    st.lists(st.integers(0, 4), min_size=1, max_size=15),
    st.booleans(),
)
async def test_execution_ledger(qty, pool, sequence, cancel_midway) -> None:
    ctx, user = make_context()
    service = OrderService(ctx)
    order = await service.create(
        user, OrderRequest("AAPL", "buy", Decimal(qty), confirmed=True), "key12345"
    )
    reconciler = OrderReconciler(ctx)
    accepted = {}
    ctx.alpaca.fills["account"] = []
    for index, number in enumerate(sequence):
        fill_qty, cents = pool[number]
        fill_id = f"20260101000000{number:03d}::{number:032d}"
        raw = {
            "id": fill_id,
            "order_id": order.alpaca_order_id,
            "qty": str(fill_qty),
            "price": str(Decimal(cents) / 100),
            "transaction_time": ctx.clock.now().isoformat(),
        }
        ctx.alpaca.fills["account"].append(raw)
        if fill_id not in accepted and sum(q for q, p in accepted.values()) + fill_qty <= qty:
            accepted[fill_id] = Decimal(fill_qty), Decimal(cents) / 100
        if cancel_midway and index == len(sequence) // 2:
            try:
                await service.cancel(user, order.id, "no_longer_needed", None, True)
            except AppError as error:
                assert error.code == "ORDER_NOT_CANCELLABLE"
        await reconciler.run_once()
        current = await ctx.uow.work.orders.get(id=order.id)
        total = sum((q for q, p in accepted.values()), Decimal(0))
        assert current.filled_qty == total <= qty
        assert current.fully_filled is (total == qty)
        if total:
            assert current.filled_avg_price == sum(q * p for q, p in accepted.values()) / total
        assert len(ctx.uow.work.executions.values) == len(accepted)
    before = list(ctx.uow.work.executions.values)
    await reconciler.run_once()
    assert ctx.uow.work.executions.values == before
    assert len([n for n in ctx.notifier.values if n[1] == "order_executions"]) == len(accepted)
