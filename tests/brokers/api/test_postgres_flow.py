from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest
import sqlalchemy as sa
from fastapi import Request

from acciones_ud.brokers.adapters.outbound.identity.broker_directory import BrokerDirectory
from acciones_ud.brokers.adapters.outbound.identity.linked_account_reader import LinkedAccountReader
from acciones_ud.brokers.adapters.outbound.persistence.unit_of_work import build_work
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.orders.adapters.outbound.persistence.unit_of_work import build_work as order_work
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.application.proposal_orders import OrderQueries, ProposalOrders
from tests.brokers.api.support import app_for
from tests.brokers.support import context
from tests.brokers.unit.test_repository_db import parties
from tests.orders.support import make_context

pytestmark = pytest.mark.db


@pytest.mark.parametrize("order_type", ["market", "limit"])
async def test_complete_broker_http_flow_uses_postgres_and_real_order_application(
    db_session, order_type
):
    ctx = context()
    investor, broker = await parties(db_session)
    for actor, role in ((investor, "investor"), (broker, "broker")):
        await db_session.execute(
            sa.text("""INSERT INTO role_assignments
            (id,user_id,role_code,valid_from) VALUES (:id,:actor,:role,:start)
        """),
            {
                "id": uuid4(),
                "actor": actor,
                "role": role,
                "start": ctx.clock.now() - timedelta(days=1),
            },
        )
    await db_session.execute(
        sa.text("""INSERT INTO kyc_accounts
        (user_id,alpaca_account_id,status,status_updated_at,reserved_at)
        VALUES (:investor,'account','ACTIVE',now(),now())
    """),
        {"investor": investor},
    )

    @asynccontextmanager
    async def sessions():
        yield db_session

    @asynccontextmanager
    async def brokers_uow():
        async with db_session.begin_nested():
            yield build_work(db_session)

    @asynccontextmanager
    async def orders_uow():
        async with db_session.begin_nested():
            yield order_work(db_session)

    order_ctx, fake_investor = make_context()
    order_ctx.accounts.values[investor] = replace(
        order_ctx.accounts.values[fake_investor], user_id=investor
    )
    order_ctx.sessions.open = False
    order_ctx.quotes.price = Decimal(100)
    order_service = OrderService(replace(order_ctx, uow=orders_uow, clock=ctx.clock))
    ctx = replace(
        ctx,
        uow=brokers_uow,
        directory=BrokerDirectory(sessions, ctx.clock),
        accounts=LinkedAccountReader(sessions),
        order_creation=ProposalOrders(order_service),
        order_query=OrderQueries(order_service),
    )
    app = app_for(ctx)

    async def current(request: Request):
        actor = UUID(request.cookies["access_token"])
        roles = {
            role for role in ("investor", "broker") if await ctx.directory.has_role(actor, role)
        }
        return CurrentUser(actor, uuid4(), "test@example.test", "active", False, frozenset(roles))

    app.dependency_overrides[get_current_user] = current
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://test"
    ) as client:
        client.cookies.set("access_token", str(investor))
        response = await client.post(
            "/api/v1/broker-links", json={"broker_id": str(broker), "consent_accepted": True}
        )
        assert response.status_code == 201, response.text
        link = response.json()["id"]
        client.cookies.set("access_token", str(broker))
        assert (await client.post(f"/api/v1/broker/link-requests/{link}/accept")).status_code == 200
        response = await client.post(
            "/api/v1/broker/proposals",
            json={
                "investor_id": str(investor),
                "symbol": "AAPL",
                "side": "buy",
                "qty": "1",
                "type": order_type,
                **({"limit_price": "100.00"} if order_type == "limit" else {}),
            },
        )
        assert response.status_code == 201, response.text
        proposal = response.json()["id"]
        message = await client.post(
            f"/api/v1/broker/proposals/{proposal}/messages", json={"body": "Evidence"}
        )
        assert message.status_code == 201, message.text
        client.cookies.set("access_token", str(investor))
        assert (
            await client.post(
                f"/api/v1/broker-links/{link}/trading-authorization",
                json={"consent_accepted": True},
            )
        ).status_code == 201
        assert (
            await client.post(
                f"/api/v1/proposals/{proposal}/decision", json={"version": 1, "decision": "accept"}
            )
        ).status_code == 200
        client.cookies.set("access_token", str(broker))
        body = {"version": 1, "decision": "approve", "evidence_message_ids": [message.json()["id"]]}
        response = await client.post(f"/api/v1/broker/proposals/{proposal}/decision", json=body)
        assert response.status_code == 200 and response.json()["status"] == "approved", (
            response.text
        )
        order_id = response.json()["order_id"]
        repeated = await client.post(f"/api/v1/broker/proposals/{proposal}/decision", json=body)
        assert repeated.json()["order_id"] == order_id
        orders = await client.get(f"/api/v1/broker/clients/{investor}/orders")
        assert orders.status_code == 200 and orders.json()["items"][0]["id"] == order_id, (
            orders.text
        )
        stored = (
            await db_session.execute(
                sa.text("""SELECT o.status, e.actor_type, e.actor_id
            FROM orders o JOIN order_events e ON e.order_id=o.id
            WHERE o.id=:id AND e.from_status IS NULL"""),
                {"id": UUID(order_id)},
            )
        ).one()
        assert (
            stored.status == "BROKER_SIGNED"
            and stored.actor_type == "broker"
            and stored.actor_id == broker
        )
        client.cookies.set("access_token", str(investor))
        ended = await client.post(
            f"/api/v1/broker-links/{link}/end", json={"reason": "Ended", "confirmed": True}
        )
        assert ended.status_code == 200, ended.text
        assert (
            await client.put(f"/api/v1/brokers/{broker}/rating", json={"stars": 5})
        ).status_code == 200
        client.cookies.set("access_token", str(broker))
        assert (await client.get(f"/api/v1/broker/clients/{investor}/orders")).status_code == 404
        assert (await client.get(f"/api/v1/broker/proposals/{proposal}")).status_code == 404
