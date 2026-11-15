from uuid import uuid4

import httpx

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from tests.orders.api.support import api_for
from tests.orders.support import make_context


async def test_preview_create_detail_list_and_cancel() -> None:
    ctx, user_id = make_context()
    app = api_for(ctx)
    user = CurrentUser(
        user_id, uuid4(), "test@example.com", "active", False, frozenset({"investor"})
    )
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        body = {"symbol": "AAPL", "side": "buy", "qty": "0.000000001", "confirmed": True}
        preview = await client.post("/api/v1/orders/preview", json=body)
        assert preview.status_code == 200, preview.text
        assert preview.json()["estimated_amount"] == "0.01"
        assert not ctx.uow.work.orders.values
        response = await client.post(
            "/api/v1/orders", json=body, headers={"Idempotency-Key": "key12345"}
        )
        assert response.status_code == 201, response.text
        document = response.json()
        assert document["qty"] == "0.000000001" and document["status"] == "SUBMITTED"
        assert document["reservation"]["status"] == "transferred"
        assert len(document["events"]) == 2
        assert "totp_code" not in response.text
        ident = document["id"]
        assert (await client.get(f"/api/v1/orders/{ident}")).json() == document
        page = await client.get("/api/v1/orders", params={"page_size": 1})
        assert page.status_code == 200 and len(page.json()["items"]) == 1
        cancel = await client.post(
            f"/api/v1/orders/{ident}/cancel", json={"reason": "price_changed", "confirmed": True}
        )
        assert cancel.status_code == 202 and cancel.json()["status"] == "SUBMITTED"
