from dataclasses import replace
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.orders.application.order_reconciler import OrderReconciler
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.domain.errors import (
    AlpacaRejectedError,
    OrderSubmissionNotReceived,
    OrderSubmissionUnknown,
)
from acciones_ud.orders.domain.model import OrderRequest
from acciones_ud.shared.domain.errors import AppError
from tests.orders.support import make_context


# Feature: orders-mod-03, Property 8: Idempotencia de la creación
@settings(max_examples=100)
@given(st.integers(1, 20), st.lists(st.booleans(), min_size=1, max_size=12))
async def test_creation_idempotency(qty, mutations) -> None:
    ctx, user = make_context()
    service = OrderService(ctx)
    request = OrderRequest("AAPL", "buy", Decimal(qty), confirmed=True)
    order = await service.create(user, request, "key12345")
    for changed in mutations:
        if changed:
            with pytest.raises(AppError) as caught:
                await service.create(user, replace(request, qty=request.qty + 1), "key12345")
            assert caught.value.code == "IDEMPOTENCY_CONFLICT"
        else:
            assert await service.create(user, request, "key12345") == order
    assert len(ctx.uow.work.orders.values) == 1
    assert ctx.alpaca.creations[order.client_order_id] == 1


# Feature: orders-mod-03, Property 9: Envío como máximo una vez por Order
@settings(max_examples=100)
@given(
    st.sampled_from(["ack", "reject", "not_received", "timeout", "5xx"]),
    st.booleans(),
    st.lists(st.booleans(), min_size=1, max_size=8),
)
async def test_at_most_once_submission(outcome, stored, lookups) -> None:
    ctx, user = make_context()
    errors = {
        "reject": AlpacaRejectedError("Rejected"),
        "not_received": OrderSubmissionNotReceived(),
        "timeout": OrderSubmissionUnknown(),
        "5xx": OrderSubmissionUnknown(server_error=True),
    }
    if outcome != "ack":
        ctx.alpaca.outcomes.append(errors[outcome])
    ctx.alpaca.store_on_unknown = stored
    service = OrderService(ctx)
    try:
        await service.create(
            user, OrderRequest("AAPL", "buy", Decimal(1), confirmed=True), "key12345"
        )
    except AppError:
        assert outcome in {"reject", "not_received", "5xx"}
    order = ctx.uow.work.orders.values[0]
    reconciler = OrderReconciler(ctx)
    misses = 0
    for found in lookups:
        ctx.alpaca.lookup_found = found
        await service.submitter.submit(order.id, waited=True)
        await reconciler.run_once()
        current = await ctx.uow.work.orders.get(id=order.id)
        if outcome == "timeout" and current.alpaca_order_id is None:
            misses += 1
            assert current.status == ("FAILED" if misses >= 2 else "SUBMITTED")
        assert ctx.alpaca.creations[order.client_order_id] == 1
    assert len(ctx.uow.work.orders.values) == 1
