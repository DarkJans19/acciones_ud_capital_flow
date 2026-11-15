from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.orders.application.reservation_ledger import ReservationLedger
from acciones_ud.orders.domain.errors import InsufficientBuyingPowerError, InsufficientPositionError
from acciones_ud.orders.domain.model import OrderStatus
from tests.orders.fakes import MemoryFactory
from tests.orders.support import make_order
from tests.support.clock import FakeClock


# Feature: orders-mod-03, Property 4: Invariante del Reservation_Ledger
@settings(max_examples=100)
@given(
    st.lists(
        st.tuples(
            st.sampled_from(["buy", "sell"]),
            st.sampled_from(["cancel", "expire", "ack", "adjust", "keep"]),
        ),
        min_size=1,
        max_size=25,
    )
)
async def test_ledger_invariant(operations) -> None:
    uow, ledger, clock, user = MemoryFactory(), ReservationLedger(), FakeClock(), uuid4()
    expected_usd = expected_shares = Decimal(0)
    for side, operation in operations:
        order = make_order(user, side=side)
        async with uow() as work:
            await work.orders.insert(order)
            await ledger.reserve(work, order, Decimal("100000"), Decimal("10000"), clock.now())
            if operation in {"cancel", "expire"}:
                order = replace(
                    order,
                    status=OrderStatus.CANCELED if operation == "cancel" else OrderStatus.EXPIRED,
                )
                await work.orders.save(order)
                await ledger.release(work, order.id, clock.now())
            elif operation == "ack":
                order = replace(order, status=OrderStatus.SUBMITTED, alpaca_order_id=str(uuid4()))
                await work.orders.save(order)
                await ledger.transfer(work, order.id, clock.now())
            else:
                if operation == "adjust":
                    order = replace(order, estimated_amount=Decimal("20.40"), qty=Decimal(2))
                    await ledger.adjust(
                        work, order, Decimal("100000"), Decimal("10000"), clock.now()
                    )
                    await work.orders.save(order)
                if side == "buy":
                    expected_usd += order.estimated_amount
                else:
                    expected_shares += order.qty
            assert await ledger.active_usd(work, user) == expected_usd
            assert await ledger.active_shares(work, user, "AAPL") == expected_shares
            assert len(work.reservations.values) == len(work.orders.values)
            for reservation in work.reservations.values:
                matching = await work.orders.get(id=reservation.order_id)
                if matching.alpaca_order_id:
                    assert reservation.status == "transferred"
                elif matching.status in {OrderStatus.CANCELED, OrderStatus.EXPIRED}:
                    assert reservation.status == "released"


# Feature: orders-mod-03, Property 5: Reservas serializadas sin sobrecompromiso
@settings(max_examples=100)
@given(
    st.integers(0, 2000),
    st.integers(0, 100),
    st.lists(st.tuples(st.sampled_from(["buy", "sell"]), st.integers(1, 20)), max_size=30),
)
async def test_no_overcommit(power, available, requests) -> None:
    uow, ledger, clock, user = MemoryFactory(), ReservationLedger(), FakeClock(), uuid4()
    usd, shares = Decimal(0), Decimal(0)
    for side, qty in requests:
        order = make_order(user, side=side, qty=Decimal(qty), estimated_amount=Decimal(qty * 10))
        accepted = (
            usd + order.estimated_amount <= power if side == "buy" else shares + qty <= available
        )
        try:
            async with uow() as work:
                await work.lock_user(user)
                await ledger.reserve(work, order, Decimal(power), Decimal(available), clock.now())
                await work.orders.insert(order)
        except (InsufficientBuyingPowerError, InsufficientPositionError):
            assert not accepted
        else:
            assert accepted
            if side == "buy":
                usd += order.estimated_amount
            else:
                shares += order.qty
        assert await ledger.active_usd(uow.work, user) == usd <= power
        assert await ledger.active_shares(uow.work, user, "AAPL") == shares <= available
