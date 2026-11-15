from decimal import Decimal
from uuid import uuid4

from acciones_ud.orders.application.order_scheduler import OrderScheduler
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.application.schedule_change import ScheduleChange, ScheduleChangeService
from acciones_ud.orders.domain.model import OrderRequest
from acciones_ud.orders.domain.model import OrderStatus as S
from tests.orders.support import make_context


async def test_schedule_change_is_once_per_investor_and_resume_recalculates() -> None:
    ctx, user = make_context()
    service = OrderService(ctx)
    ctx.sessions.open = False
    request = OrderRequest("AAPL", "buy", Decimal(1), confirmed=True, schedule_if_closed=True)
    first = await service.create(user, request, "key12345")
    second = await service.create(user, request, "key12346")
    change = ScheduleChange(uuid4(), "NASDAQ", ctx.clock.now().date(), "Holiday schedule")
    change_service = ScheduleChangeService(ctx)
    result = await change_service.apply(change, ctx.clock.now())
    assert set(result.affected_order_ids) == {first.id, second.id}
    assert not result.already_applied
    assert len(ctx.notifier.values) == 1
    assert (await change_service.apply(change, ctx.clock.now())).already_applied
    assert len(ctx.notifier.values) == 1
    await OrderScheduler(ctx, service).run_once()
    assert not ctx.alpaca.creations
    ctx.clock.advance(7200)
    resumed = await service.resume(user, first.id)
    assert resumed.status == S.PENDING and resumed.scheduled_for > first.scheduled_for
    ctx.sessions.open = True
    ctx.clock.advance(3600)
    await OrderScheduler(ctx, service).run_once()
    assert (await ctx.uow.work.orders.get(id=first.id)).status == S.SUBMITTED
    assert (await ctx.uow.work.orders.get(id=second.id)).status == S.IN_REVIEW
    assert sum(ctx.alpaca.creations.values()) == 1


async def test_missed_day_session_expires_before_scheduler_can_send() -> None:
    ctx, user = make_context()
    ctx.sessions.open = False
    service = OrderService(ctx)
    order = await service.create(
        user,
        OrderRequest("AAPL", "buy", Decimal(1), confirmed=True, schedule_if_closed=True),
        "key12345",
    )
    ctx.clock.advance(8 * 3600)
    ctx.sessions.open = True
    await OrderScheduler(ctx, service).run_once()
    assert (await ctx.uow.work.orders.get(id=order.id)).status == S.EXPIRED
    assert (await ctx.uow.work.reservations.get(order_id=order.id)).status == "released"
    assert not ctx.alpaca.creations
