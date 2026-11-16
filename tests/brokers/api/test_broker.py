from fastapi.testclient import TestClient

from tests.brokers.api.support import app_for
from tests.brokers.support import actors, context


def test_http_link_proposal_messages_acceptance_and_approval():
    ctx = context()
    investor, broker = actors(ctx)
    client = TestClient(app_for(ctx))
    client.cookies.set("access_token", str(investor))
    requested = client.post(
        "/api/v1/broker-links", json={"broker_id": str(broker), "consent_accepted": True}
    )
    link_id = requested.json()["id"]
    client.cookies.set("access_token", str(broker))
    assert client.post(f"/api/v1/broker/link-requests/{link_id}/accept").status_code == 200
    created = client.post(
        "/api/v1/broker/proposals",
        json={
            "investor_id": str(investor),
            "symbol": "AAPL",
            "side": "buy",
            "qty": "1",
            "type": "market",
        },
    )
    assert created.status_code == 201, created.text
    proposal_id = created.json()["id"]
    message = client.post(
        f"/api/v1/broker/proposals/{proposal_id}/messages", json={"body": "Evidence"}
    )
    assert message.status_code == 201
    client.cookies.set("access_token", str(investor))
    assert (
        client.post(
            f"/api/v1/broker-links/{link_id}/trading-authorization", json={"consent_accepted": True}
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/v1/proposals/{proposal_id}/decision", json={"version": 1, "decision": "accept"}
        ).status_code
        == 200
    )
    client.cookies.set("access_token", str(broker))
    approved = client.post(
        f"/api/v1/broker/proposals/{proposal_id}/decision",
        json={"version": 1, "decision": "approve", "evidence_message_ids": [message.json()["id"]]},
    )
    assert approved.status_code == 200 and approved.json()["status"] == "approved", approved.text
    assert len(ctx.order_creation.orders) == 1
    clients = client.get("/api/v1/broker/clients")
    assert clients.status_code == 200 and clients.json()[0]["trading_authorized"]
    orders = client.get(f"/api/v1/broker/clients/{investor}/orders")
    assert orders.status_code == 200, orders.text
