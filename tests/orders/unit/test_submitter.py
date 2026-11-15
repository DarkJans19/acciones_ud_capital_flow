import pytest

from acciones_ud.orders.application.order_submitter import OrderSubmitter
from acciones_ud.orders.application.reservation_ledger import ReservationLedger
from acciones_ud.orders.domain.errors import (
    AlpacaRejectedError,
    OrderSubmissionNotReceived,
    OrderSubmissionUnknown,
)
from acciones_ud.orders.domain.model import OrderStatus as S
from tests.orders.support import make_context, make_order


@pytest.mark.parametrize(
    "outcome,status,reservation",
    [
        (None, S.SUBMITTED, "transferred"),
        (AlpacaRejectedError("Rejected"), S.REJECTED, "released"),
        (OrderSubmissionNotReceived(), S.FAILED, "released"),
        (OrderSubmissionUnknown(), S.SUBMITTED, "active"),
    ],
)
async def test_submitter_persists_outcome(outcome, status, reservation) -> None:
    context, user = make_context()
    order = make_order(user)
    async with context.uow() as work:
        await work.orders.insert(order)
        await ReservationLedger().reserve(work, order, 1000, 1000, context.clock.now())
    if outcome:
        context.alpaca.outcomes.append(outcome)
    try:
        await OrderSubmitter(context).submit(order.id, waited=False)
    except (AlpacaRejectedError, OrderSubmissionNotReceived):
        pass
    except Exception as caught:
        assert caught.code in {"ORDER_REJECTED", "ALPACA_UNAVAILABLE"}
    async with context.uow() as work:
        assert (await work.orders.get(id=order.id)).status == status
        assert (await work.reservations.get(order_id=order.id)).status == reservation
    await OrderSubmitter(context).submit(order.id, waited=False)
    assert context.alpaca.creations[order.client_order_id] == 1
