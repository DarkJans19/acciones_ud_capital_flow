from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

import httpx
from hypothesis import given, settings
from hypothesis import strategies as st

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.domain.model import OrderRequest
from tests.orders.api.support import api_for
from tests.orders.support import make_context


# Feature: orders-mod-03, Property 11: Propiedad de recursos sin filtración
@settings(max_examples=100)
@given(st.uuids(), st.sampled_from(["investor", "broker"]), st.integers(1, 20))
async def test_foreign_resources_equal_missing(actor, role, qty) -> None:
    ctx, owner = make_context()
    if actor == owner:
        actor = uuid4()
    order = await OrderService(ctx).create(
        owner, OrderRequest("AAPL", "buy", Decimal(qty), confirmed=True), "key12345"
    )
    app = api_for(ctx)
    user = CurrentUser(actor, uuid4(), "other@example.com", "active", False, frozenset({role}))
    app.dependency_overrides[get_current_user] = lambda: user
    operations = (
        [
            ("GET", "/api/v1/orders/{id}", None),
            ("POST", "/api/v1/orders/{id}/cancel", {"reason": "input_error", "confirmed": True}),
            ("POST", "/api/v1/orders/{id}/reauthorization", {"decision": "accept"}),
            ("POST", "/api/v1/orders/{id}/resubmit", {"qty": "2"}),
            ("POST", "/api/v1/orders/{id}/resume", None),
        ]
        if role == "investor"
        else [
            ("POST", "/api/v1/broker/order-reviews/{id}/return", {"comment": "Review"}),
            ("POST", "/api/v1/broker/order-reviews/{id}/approve", None),
        ]
    )
    before = deepcopy(
        (
            ctx.uow.work.orders.values,
            ctx.uow.work.events.values,
            ctx.uow.work.reservations.values,
            ctx.uow.work.cancels.values,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        for method, path, body in operations:
            responses = []
            for ident in (order.id, uuid4()):
                response = await client.request(method, path.format(id=ident), json=body)
                assert response.status_code == 404, response.text
                responses.append(response.json())
            assert responses[0] == responses[1]
            assert responses[0]["code"] == "ORDER_NOT_FOUND"
    assert before == (
        ctx.uow.work.orders.values,
        ctx.uow.work.events.values,
        ctx.uow.work.reservations.values,
        ctx.uow.work.cancels.values,
    )
    assert ctx.alpaca.creations[order.client_order_id] == 1


async def test_each_endpoint_requires_session_and_correct_role() -> None:
    ctx, _ = make_context()
    app = api_for(ctx)
    operations = [
        (method, path.replace("{id}", str(uuid4())))
        for path, methods in app.openapi()["paths"].items()
        for method in methods
    ]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        for method, path in operations:
            app.dependency_overrides.clear()
            response = await client.request(method, path)
            assert response.status_code == 401, (path, response.text)
            wrong_role = "investor" if "/broker/" in path else "broker"
            user = CurrentUser(
                uuid4(), uuid4(), "wrong@example.com", "active", False, frozenset({wrong_role})
            )
            app.dependency_overrides[get_current_user] = lambda user=user: user
            response = await client.request(method, path)
            assert response.status_code == 403, (path, response.text)
    assert not ctx.alpaca.creations
