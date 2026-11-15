from uuid import uuid4

import httpx

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from tests.orders.api.support import api_for
from tests.orders.support import make_context


async def test_broker_review_workflow_via_api() -> None:
    ctx, investor = make_context()
    broker = uuid4()
    ctx.brokers.links[investor] = broker
    app = api_for(ctx)
    user = CurrentUser(
        investor, uuid4(), "investor@example.com", "active", False, frozenset({"investor"})
    )
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        response = await client.post(
            "/api/v1/orders",
            headers={"Idempotency-Key": "key12345"},
            json={"symbol": "AAPL", "side": "buy", "qty": "1", "confirmed": True},
        )
        assert response.status_code == 201 and response.json()["status"] == "IN_REVIEW"
        ident = response.json()["id"]
        investor_user = user
        user = CurrentUser(
            broker, uuid4(), "broker@example.com", "active", False, frozenset({"broker"})
        )
        queue = await client.get("/api/v1/broker/order-reviews")
        assert queue.status_code == 200 and queue.json()[0]["id"] == ident
        response = await client.post(
            f"/api/v1/broker/order-reviews/{ident}/return", json={"comment": "Adjust quantity"}
        )
        assert response.status_code == 200 and response.json()["returned_for_changes"]
        broker_user, user = user, investor_user
        response = await client.post(f"/api/v1/orders/{ident}/resubmit", json={"qty": "2"})
        assert response.status_code == 200 and response.json()["status"] == "IN_REVIEW"
        user = broker_user
        response = await client.post(f"/api/v1/broker/order-reviews/{ident}/approve")
        assert response.status_code == 200 and response.json()["status"] == "SUBMITTED"
        assert response.json()["broker_id"] == str(broker)
