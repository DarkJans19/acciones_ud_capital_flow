import re

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


def test_all_broker_endpoints_in_a_complete_investor_and_broker_journey():
    ctx = context()
    investor, broker = actors(ctx)
    app = app_for(ctx)
    client = TestClient(app)
    covered = set()

    def actor(identity):
        client.cookies.set("access_token", str(identity))

    def call(method, path, expected=200, **kwargs):
        response = client.request(method, path, **kwargs)
        assert response.status_code == expected, (method, path, response.text)
        template = next(
            template for template, operations in app.openapi()["paths"].items()
            if method.lower() in operations
            and re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", template), path)
        )
        covered.add((method.lower(), template))
        return response.json()

    actor(investor)
    call("GET", "/api/v1/brokers")
    call("GET", "/api/v1/brokers/suggestions")
    call("GET", f"/api/v1/brokers/{broker}")
    call("GET", f"/api/v1/brokers/{broker}/reputation")
    call("GET", f"/api/v1/brokers/{broker}/reviews")
    call("GET", "/api/v1/broker-links/current")
    link_body = {"broker_id": str(broker), "consent_accepted": True}
    canceled = call("POST", "/api/v1/broker-links", 201, json=link_body)["id"]
    call("POST", f"/api/v1/broker-links/{canceled}/cancel")
    declined = call("POST", "/api/v1/broker-links", 201, json=link_body)["id"]
    actor(broker)
    call("GET", "/api/v1/broker/link-requests")
    call("POST", f"/api/v1/broker/link-requests/{declined}/decline", json={"reason": "Unavailable"})
    call("PUT", "/api/v1/brokers/me/profile", json={"specialty": "Equities", "years_experience": 5})
    actor(investor)
    link = call("POST", "/api/v1/broker-links", 201, json=link_body)["id"]
    actor(broker)
    call("POST", f"/api/v1/broker/link-requests/{link}/accept")
    actor(investor)
    call("PUT", f"/api/v1/broker-links/{link}/order-review", json={"enabled": True})
    call(
        "POST",
        f"/api/v1/broker-links/{link}/trading-authorization",
        201,
        json={"consent_accepted": True},
    )
    call("POST", f"/api/v1/broker-links/{link}/trading-authorization/revoke")
    call(
        "POST",
        f"/api/v1/broker-links/{link}/trading-authorization",
        201,
        json={"consent_accepted": True},
    )
    actor(broker)
    content = {"symbol": "AAPL", "side": "buy", "qty": "1", "type": "market"}
    proposal_body = {"investor_id": str(investor), **content}
    withdrawn = call("POST", "/api/v1/broker/proposals", 201, json=proposal_body)["id"]
    modified = call(
        "PUT", f"/api/v1/broker/proposals/{withdrawn}", json={"version": 1, **content, "qty": "2"}
    )
    call(
        "POST",
        f"/api/v1/broker/proposals/{withdrawn}/withdraw",
        json={"version": modified["current_version"], "reason": "Replaced", "confirmed": True},
    )
    proposal = call("POST", "/api/v1/broker/proposals", 201, json=proposal_body)["id"]
    call("GET", "/api/v1/broker/proposals")
    call("GET", f"/api/v1/broker/proposals/{proposal}")
    evidence = call(
        "POST",
        f"/api/v1/broker/proposals/{proposal}/messages",
        201,
        json={"body": "Investment rationale"},
    )
    call("GET", f"/api/v1/broker/proposals/{proposal}/messages")
    actor(investor)
    call("GET", "/api/v1/proposals")
    call("GET", f"/api/v1/proposals/{proposal}")
    call("POST", f"/api/v1/proposals/{proposal}/messages", 201, json={"body": "Reviewed"})
    call("GET", f"/api/v1/proposals/{proposal}/messages")
    call(
        "POST", f"/api/v1/proposals/{proposal}/decision", json={"version": 1, "decision": "accept"}
    )
    actor(broker)
    approved = call(
        "POST",
        f"/api/v1/broker/proposals/{proposal}/decision",
        json={"version": 1, "decision": "approve", "evidence_message_ids": [evidence["id"]]},
    )
    assert approved["order_id"] and len(ctx.order_creation.orders) == 1
    call("GET", "/api/v1/broker/clients")
    call("GET", f"/api/v1/broker/clients/{investor}/orders")
    actor(investor)
    call(
        "POST", f"/api/v1/broker-links/{link}/end", json={"reason": "Completed", "confirmed": True}
    )
    call("GET", "/api/v1/broker-links")
    call("PUT", f"/api/v1/brokers/{broker}/rating", json={"stars": 5, "comment": "Helpful"})
    expected = {(method, path) for path, ops in app.openapi()["paths"].items() for method in ops}
    assert covered == expected
