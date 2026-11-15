from dataclasses import replace
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.application.order_submitter import OrderSubmitter
from acciones_ud.orders.application.reservation_ledger import ReservationLedger
from acciones_ud.orders.domain.estimates import estimated_amount
from acciones_ud.orders.domain.model import OrderRequest
from acciones_ud.orders.domain.model import OrderStatus as S
from acciones_ud.shared.domain.errors import AppError
from tests.orders.support import make_context, make_order


# Feature: orders-mod-03, Property 6: Detección de cambio de precio y bloqueo de envío
@settings(max_examples=100)
@given(
    st.sampled_from(["market", "limit", "stop", "stop_limit", "trailing_stop"]),
    st.booleans(),
    st.decimals(1, 1000, places=2),
    st.decimals(1, 1000, places=2),
    st.decimals("0.01", 100, places=2),
)
async def test_price_change_prevents_submission(
    kind, waited, reference, current, threshold
) -> None:
    ctx, user = make_context()
    ctx = replace(ctx, config=replace(ctx.config, reauth_deviation_pct=threshold))
    ctx.quotes.price, ctx.buying_power.value = current, Decimal("1000000")
    order = make_order(
        user,
        type=kind,
        reference_price=reference,
        estimated_amount=estimated_amount("buy", Decimal(1), reference, ctx.config.commission_rate),
        limit_price=Decimal(10) if kind in {"limit", "stop_limit"} else None,
        stop_price=Decimal(9) if kind in {"stop", "stop_limit"} else None,
        trail_percent=Decimal(1) if kind == "trailing_stop" else None,
    )
    async with ctx.uow() as work:
        await work.orders.insert(order)
        await ReservationLedger().reserve(work, order, 1000000, 1000000, ctx.clock.now())
    result = await OrderSubmitter(ctx).submit(order.id, waited)
    expected_held = (
        kind == "market" and waited and abs(current - reference) / reference * 100 > threshold
    )
    assert (result.status == S.HELD) == expected_held
    assert ctx.alpaca.creations[order.client_order_id] == (0 if expected_held else 1)
    if expected_held:
        await OrderSubmitter(ctx).submit(order.id, False)
        await OrderSubmitter(ctx).submit(order.id, True)
        from acciones_ud.orders.application.order_scheduler import OrderScheduler

        await OrderScheduler(ctx, OrderService(ctx)).run_once()
        assert ctx.alpaca.creations[order.client_order_id] == 0


# Feature: orders-mod-03, Property 7: Respuesta a la nueva autorización
@settings(max_examples=100)
@given(
    st.sampled_from(["accept", "reject", "none"]),
    st.sampled_from([-1, 0, 1]),
    st.integers(0, 2000),
    st.decimals(20, 1000, places=2),
    st.booleans(),
)
async def test_reauthorization_answer(decision, offset, funds, price, market_open) -> None:
    ctx, user = make_context()
    ctx.sessions.open = False
    service = OrderService(ctx)
    order = await service.create(
        user,
        OrderRequest("AAPL", "buy", Decimal(1), confirmed=True, schedule_if_closed=True),
        "key12345",
    )
    ctx.sessions.open, ctx.quotes.price = True, price
    held = await service.submitter.submit(order.id, waited=True)
    assert held.status == S.HELD
    ctx.sessions.open, ctx.buying_power.value = market_open, Decimal(funds)
    ctx.clock.advance(1800 + offset)
    if decision == "none":
        await service.expire_stale()
    elif offset >= 0:
        with pytest.raises(AppError) as caught:
            await service.answer_reauthorization(user, order.id, decision)
        assert caught.value.code == "INVALID_ORDER_STATE"
    elif decision == "accept" and Decimal(funds) < estimated_amount(
        "buy", Decimal(1), price, ctx.config.commission_rate
    ):
        with pytest.raises(AppError) as caught:
            await service.answer_reauthorization(user, order.id, decision)
        assert caught.value.code == "INSUFFICIENT_BUYING_POWER"
    else:
        await service.answer_reauthorization(user, order.id, decision)
    current = await ctx.uow.work.orders.get(id=order.id)
    reservation = await ctx.uow.work.reservations.get(order_id=order.id)
    response = ctx.uow.work.reauthorizations.values[0]
    if offset >= 0:
        assert current.status == S.EXPIRED and reservation.status == "released"
        assert response.decision == "no_response" and response.answered_at == ctx.clock.now()
    elif decision == "reject":
        assert current.status == S.CANCELED and reservation.status == "released"
        assert response.decision == "rejected" and response.answered_at == ctx.clock.now()
    elif decision == "accept" and Decimal(funds) >= estimated_amount(
        "buy", Decimal(1), price, ctx.config.commission_rate
    ):
        assert current.status == (S.SUBMITTED if market_open else S.PENDING)
        assert current.reference_price == price
        assert current.estimated_amount == reservation.amount
        assert response.decision == "accepted" and response.answered_at == ctx.clock.now()
        assert reservation.status == ("transferred" if market_open else "active")
    else:
        assert current.status == S.HELD and reservation.amount == held.estimated_amount
        assert response.decision is None
