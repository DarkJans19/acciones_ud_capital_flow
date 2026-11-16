import asyncio
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.orders.application.order_reconciler import OrderReconciler
from tests.orders.api.support import api_for
from tests.orders.support import make_context


@pytest.mark.parametrize("value", [-1, 121, float("inf"), float("nan")])
def test_deadline_rejects_invalid_configuration(value) -> None:
    from acciones_ud.config.settings import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, order_creation_deadline_seconds=value)


async def test_disabled_deadline_allows_slow_creation_without_duplicate_submission() -> None:
    ctx, owner = make_context()
    original = ctx.alpaca.create

    async def delayed(account_id, submission, timeout_s):
        await asyncio.sleep(0.05)
        return await original(account_id, submission, timeout_s)

    ctx.alpaca.create = delayed
    app = api_for(ctx)
    app.state.settings.order_creation_deadline_seconds = 0
    user = CurrentUser(
        owner, uuid4(), "owner@example.com", "active", False, frozenset({"investor"})
    )
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        body = {"symbol": "AAPL", "side": "buy", "qty": "1", "confirmed": True}
        first = await client.post(
            "/api/v1/orders", json=body, headers={"Idempotency-Key": "disabled-deadline"}
        )
        second = await client.post(
            "/api/v1/orders", json=body, headers={"Idempotency-Key": "disabled-deadline"}
        )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert sum(ctx.alpaca.creations.values()) == 1


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
    app.state.settings.order_creation_deadline_seconds = 0.02
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
