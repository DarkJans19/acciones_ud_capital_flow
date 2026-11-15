import asyncio
from uuid import uuid4

import httpx

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.orders.adapters.inbound.http.routers import orders as router_module
from acciones_ud.orders.application.order_reconciler import OrderReconciler
from tests.orders.api.support import api_for
from tests.orders.support import make_context


async def test_response_deadline_preserves_staged_order_for_idempotent_retry(monkeypatch) -> None:
    ctx, owner = make_context()
    original = ctx.alpaca.create

    async def delayed(account_id, submission, timeout_s):
        result = await original(account_id, submission, timeout_s)
        await asyncio.sleep(1)
        return result

    ctx.alpaca.create = delayed
    app = api_for(ctx)
    user = CurrentUser(
        owner, uuid4(), "owner@example.com", "active", False, frozenset({"investor"})
    )
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(router_module, "CREATION_DEADLINE_SECONDS", 0.02)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        body = {"symbol": "AAPL", "side": "buy", "qty": "1", "confirmed": True}
        response = await client.post(
            "/api/v1/orders", json=body, headers={"Idempotency-Key": "key12345"}
        )
        assert response.status_code == 502
        assert ctx.uow.work.orders.values[0].status == "SUBMITTED"
        ctx.alpaca.create = original
        response = await client.post(
            "/api/v1/orders", json=body, headers={"Idempotency-Key": "key12345"}
        )
        assert response.status_code == 201
        assert sum(ctx.alpaca.creations.values()) == 1
        await OrderReconciler(ctx).run_once()
        assert ctx.uow.work.orders.values[0].alpaca_order_id
