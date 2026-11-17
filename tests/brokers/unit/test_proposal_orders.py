from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest

from acciones_ud.brokers.domain.ports import OrderCreated, OrderRejected, ProposalOrderCommand
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.application.proposal_orders import OrderQueries, ProposalOrders
from acciones_ud.shared.domain.errors import AppError
from tests.orders.support import make_context


async def test_proposal_order_is_signed_scheduled_and_idempotent():
    ctx, investor = make_context()
    ctx.sessions.open = False
    command = ProposalOrderCommand(
        uuid4(), investor, uuid4(), "AAPL", "buy", Decimal(1), "market", None
    )
    service = ProposalOrders(OrderService(ctx))
    first = await service.create_from_proposal(command)
    assert isinstance(first, OrderCreated)
    assert await service.create_from_proposal(command) == first
    assert await service.create_from_proposal(replace(command, qty=Decimal(2))) == OrderRejected(
        "IDEMPOTENCY_CONFLICT"
    )
    queries = OrderQueries(service.service)
    assert (
        await queries.find_by_idempotency_key(investor, f"proposal:{command.proposal_id}", command)
        == first.order_id
    )
    assert (
        await queries.find_by_idempotency_key(
            investor, f"proposal:{command.proposal_id}", replace(command, qty=Decimal(2))
        )
        is None
    )
    order = await ctx.uow.work.orders.get(id=first.order_id)
    assert order.status == "BROKER_SIGNED" and order.scheduled_for
    events = await ctx.uow.work.events.list(order_id=order.id)
    assert events[0].actor_type == "broker" and events[0].actor_id == command.broker_id
    assert events[0].cause == f"proposal:{command.proposal_id}"


async def test_proposal_order_submits_once_bypasses_only_extra_authorization():
    ctx, investor = make_context()
    ctx.controls.value = replace(ctx.controls.value, high_order_threshold_usd=Decimal(1))
    ctx.totp.active, ctx.totp.valid = False, False
    command = ProposalOrderCommand(
        uuid4(), investor, uuid4(), "AAPL", "buy", Decimal(1), "market", None
    )
    service = ProposalOrders(OrderService(ctx))
    created = await service.create(command)
    assert isinstance(created, OrderCreated)
    assert (await ctx.uow.work.orders.get(id=created.order_id)).status == "SUBMITTED"
    assert await service.create(command) == created
    assert sum(ctx.alpaca.creations.values()) == 1
    ctx.assets.values.clear()
    rejected = await service.create(replace(command, proposal_id=uuid4()))
    assert rejected == OrderRejected("ASSET_NOT_TRADABLE")
    assert len(ctx.uow.work.orders.values) == 1


async def test_proposal_order_unavailable_before_commit_propagates():
    ctx, investor = make_context()
    ctx.quotes.price = None
    command = ProposalOrderCommand(
        uuid4(), investor, uuid4(), "AAPL", "buy", Decimal(1), "market", None
    )
    with pytest.raises(AppError) as caught:
        await ProposalOrders(OrderService(ctx)).create(command)
    assert caught.value.code == "QUOTE_UNAVAILABLE"
    assert ctx.uow.work.orders.values == []


@pytest.mark.parametrize(
    ("price", "accepted"),
    [("100.0000", True), ("100.0010", False), ("0.12340000", True), ("0.12345000", False)],
)
async def test_persisted_limit_prices_preserve_value_without_false_scale_errors(price, accepted):
    ctx, investor = make_context()
    ctx.sessions.open = False
    command = ProposalOrderCommand(
        uuid4(), investor, uuid4(), "AAPL", "buy", Decimal(1), "limit", Decimal(price)
    )
    result = await ProposalOrders(OrderService(ctx)).create(command)
    if accepted:
        assert isinstance(result, OrderCreated)
        order = await ctx.uow.work.orders.get(id=result.order_id)
        assert order.limit_price == Decimal(price)
        # SQL hydration adds a fixed scale; opening later must revalidate the same value.
        hydrated = replace(order, limit_price=Decimal(price))
        await ctx.uow.work.orders.save(hydrated)
        ctx.sessions.open = True
        submitted = await OrderService(ctx).submitter.submit(order.id, waited=True)
        assert submitted.status == "SUBMITTED"
    else:
        assert result == OrderRejected("VALIDATION_ERROR")
        assert ctx.uow.work.orders.values == []
