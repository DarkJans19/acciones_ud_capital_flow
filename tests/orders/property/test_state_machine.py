from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.orders.application.context import change
from acciones_ud.orders.domain.errors import InvalidTransitionError
from acciones_ud.orders.domain.model import OrderStatus as S
from acciones_ud.orders.domain.state_machine import transition
from acciones_ud.orders.domain.status_mapping import map_alpaca
from tests.orders.support import make_context, make_order

EXPECTED = {
    "PENDING": "IN_REVIEW SUBMITTED HELD CANCELED REJECTED EXPIRED FAILED".split(),
    "IN_REVIEW": "PENDING BROKER_SIGNED CANCELED EXPIRED".split(),
    "BROKER_SIGNED": "IN_REVIEW SUBMITTED HELD CANCELED REJECTED EXPIRED FAILED".split(),
    "HELD": "PENDING BROKER_SIGNED IN_REVIEW SUBMITTED CANCELED REJECTED EXPIRED FAILED".split(),
    "SUBMITTED": "EXECUTING CANCELED REJECTED EXPIRED FAILED".split(),
    "EXECUTING": "EXECUTING CANCELED EXPIRED".split(),
}


# Feature: orders-mod-03, Property 2: Máquina de estados cerrada y terminales inmutables
@settings(max_examples=100)
@given(
    st.sampled_from(list(S)),
    st.lists(st.tuples(st.sampled_from(list(S)), st.booleans()), min_size=1, max_size=30),
)
def test_state_sequences(initial, events) -> None:
    current = initial
    for target, filled in events:
        terminal = current in {S.CANCELED, S.REJECTED, S.EXPIRED, S.FAILED} or (
            current == S.EXECUTING and filled
        )
        if not terminal and target in EXPECTED.get(current, []):
            current = transition(current, target, filled)
            assert current == target
        else:
            before = current
            with pytest.raises(InvalidTransitionError):
                transition(current, target, filled)
            assert current == before
        assert current in list(S)


# Feature: orders-mod-03, Property 3: Mapeo de estados de Alpaca
@settings(max_examples=100)
@given(
    st.one_of(
        st.text(),
        st.sampled_from(
            [
                "new",
                "accepted",
                "pending_new",
                "accepted_for_bidding",
                "calculated",
                "held",
                "stopped",
                "suspended",
                "pending_cancel",
                "pending_replace",
                "partially_filled",
                "filled",
                "done_for_day",
                "canceled",
                "expired",
                "rejected",
                "replaced",
            ]
        ),
    ),
    st.decimals(0, 100, places=9),
)
def test_provider_mapping(status, quantity) -> None:
    groups = {
        S.SUBMITTED: "new accepted pending_new accepted_for_bidding calculated held stopped "
        "suspended pending_cancel pending_replace",
        S.EXECUTING: "partially_filled filled",
        S.CANCELED: "canceled",
        S.EXPIRED: "expired",
        S.REJECTED: "rejected",
    }
    expected = next((state for state, names in groups.items() if status in names.split()), None)
    if status == "done_for_day":
        expected = S.EXECUTING if quantity > Decimal(0) else S.SUBMITTED
    assert map_alpaca(status, quantity) == expected


# Feature: orders-mod-03, Property 2: Transiciones y eventos atómicos
@settings(max_examples=100)
@given(st.sampled_from(list(S)), st.lists(st.sampled_from(list(S)), min_size=1, max_size=20))
async def test_transition_events_are_atomic(initial, targets) -> None:
    ctx, user = make_context()
    order = make_order(user, status=initial, fully_filled=initial == S.EXECUTING)
    await ctx.uow.work.orders.insert(order)
    expected_count = 0
    for target in targets:
        terminal = order.status in {S.CANCELED, S.REJECTED, S.EXPIRED, S.FAILED} or (
            order.status == S.EXECUTING and order.fully_filled
        )
        before = order
        if not terminal and target in EXPECTED.get(order.status, []):
            async with ctx.uow() as work:
                order = await change(work, order, target, "property_test", ctx.clock.now())
            expected_count += 1
        else:
            with pytest.raises(InvalidTransitionError):
                async with ctx.uow() as work:
                    await change(work, order, target, "property_test", ctx.clock.now())
            assert await ctx.uow.work.orders.get(id=order.id) == before
        assert len(ctx.uow.work.events.values) == expected_count
