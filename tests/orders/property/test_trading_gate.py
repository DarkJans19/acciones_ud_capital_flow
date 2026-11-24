import asyncio
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.domain.model import OrderRequest, OrderStatus
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.shared.domain.trading import CommissionTerms, GateDecision
from tests.orders.support import make_context


class Gate:
    def __init__(self, code):
        self.code, self.calls = code, 0

    async def check(self, user_id, exchange, at):
        self.calls += 1
        if self.code == "DATABASE_UNAVAILABLE":
            raise AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Unavailable")
        return GateDecision(self.code is None, self.code, {})


class Terms:
    def __init__(self, rate):
        self.rate = rate
        self.version = uuid4()

    async def terms(self, exchange, at):
        return CommissionTerms(self.version, self.rate, Decimal(60))


# Feature: admin-mod-07, Property 8: Bloqueo de órdenes sin llamadas a Alpaca
@settings(max_examples=100)
@given(
    st.sampled_from(["TRADING_HALTED", "ACCOUNT_TRADING_RESTRICTED", "DATABASE_UNAVAILABLE"]),
    st.sampled_from(["preview", "create", "submit"]),
    st.integers(1, 20),
)
def test_trading_gate_blocks_before_order_writes_or_provider(code, operation, repeats):
    async def run():
        context, user = make_context()
        gate = Gate(code)
        request = OrderRequest("AAPL", "buy", Decimal(1), confirmed=True, schedule_if_closed=True)
        if operation == "submit":
            context.sessions.open = False
            order = await OrderService(context).create(user, request, "scheduled-order")
            context.sessions.open = True
            blocked = OrderService(replace(context, trading_gate=gate))
            before = sum(context.alpaca.creations.values())
            for _ in range(repeats):
                if code == "DATABASE_UNAVAILABLE":
                    with pytest.raises(AppError):
                        await blocked.submitter.submit(order.id, waited=True)
                else:
                    result = await blocked.submitter.submit(order.id, waited=True)
                    assert result.status == OrderStatus.PENDING
                    assert result.scheduled_for is not None
            assert sum(context.alpaca.creations.values()) == before
            if code != "DATABASE_UNAVAILABLE":
                events = await context.uow.work.events.list(order_id=order.id)
                assert sum(e.metadata.get("deferred_by") == code.lower() for e in events) == 1
        else:
            blocked = OrderService(replace(context, trading_gate=gate))
            with pytest.raises(AppError) as caught:
                if operation == "create":
                    await blocked.create(user, request, "blocked-order")
                else:
                    await blocked.preview(user, request)
            assert caught.value.code.value == code
            assert not context.uow.work.orders.values
            assert not context.uow.work.reservations.values
            assert not context.alpaca.creations

    asyncio.run(run())


async def test_order_terms_survive_configuration_changes_and_revalidation():
    context, user = make_context()
    context.sessions.open = False
    terms = Terms(Decimal("1.7500"))
    service = OrderService(replace(context, commission_terms=terms))
    order = await service.create(
        user,
        OrderRequest("AAPL", "buy", Decimal(1), confirmed=True, schedule_if_closed=True),
        "fixed-terms-order",
    )
    assert order.commission_rate_pct == Decimal("1.7500")
    original_version, original_estimate = order.fee_version_id, order.estimated_amount
    terms.rate, terms.version = Decimal("9"), uuid4()
    context.sessions.open = True
    sent = await service.submitter.submit(order.id, waited=True)
    assert sent.fee_version_id == original_version
    assert sent.commission_rate_pct == Decimal("1.7500")
    assert sent.estimated_amount == original_estimate


@pytest.mark.parametrize("code", ["TRADING_HALTED", "ACCOUNT_TRADING_RESTRICTED"])
async def test_proposal_conversion_distinguishes_unavailability_and_business_rejection(code):
    from acciones_ud.brokers.domain.ports import OrderRejected, ProposalOrderCommand
    from acciones_ud.orders.application.proposal_orders import ProposalOrders

    context, user = make_context()
    service = ProposalOrders(OrderService(replace(context, trading_gate=Gate(code))))
    command = ProposalOrderCommand(
        uuid4(), user, uuid4(), "AAPL", "buy", Decimal(1), "market", None
    )
    if code == "TRADING_HALTED":
        with pytest.raises(AppError) as caught:
            await service.create(command)
        assert caught.value.status == 503 and caught.value.code == ErrorCode.TRADING_HALTED
    else:
        assert await service.create(command) == OrderRejected("ACCOUNT_TRADING_RESTRICTED")
    assert not context.uow.work.orders.values and not context.alpaca.creations
