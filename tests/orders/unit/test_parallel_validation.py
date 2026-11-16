import asyncio
from decimal import Decimal

from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.domain.model import OrderRequest
from tests.orders.support import make_context


async def test_quote_and_controls_reads_overlap_without_skipping_validation() -> None:
    ctx, user = make_context()
    controls_started = asyncio.Event()
    original_controls = ctx.controls.get

    async def quote(symbol):
        await asyncio.wait_for(controls_started.wait(), timeout=1)
        return Decimal("10")

    async def controls(user_id):
        controls_started.set()
        return await original_controls(user_id)

    ctx.quotes.current_price = quote
    ctx.controls.get = controls
    view = await OrderService(ctx).preview(
        user, OrderRequest("AAPL", "buy", Decimal("1"), "market", "simple", "day")
    )
    assert view["reference_price"] == Decimal("10")
    assert view["estimated_amount"] == Decimal("10.20")
