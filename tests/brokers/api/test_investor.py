from uuid import uuid4

from fastapi.testclient import TestClient

from tests.brokers.api.support import app_for
from tests.brokers.support import actors, context
from tests.brokers.unit.test_proposals import proposal_fixture


def test_directory_lists_every_broker_across_pages_without_a_search_filter():
    ctx = context()
    investor, broker = actors(ctx)
    expected = {str(broker)}
    for _ in range(12):
        ident = uuid4()
        ctx.directory.add(ident, "broker")
        expected.add(str(ident))
    ctx.directory.add(investor, "broker")
    client = TestClient(app_for(ctx))
    assert client.get("/api/v1/brokers").status_code == 401
    client.cookies.set("access_token", str(investor))
    cursor = None
    found = []
    while True:
        params = {"page_size": 5}
        if cursor:
            params["cursor"] = cursor
        response = client.get("/api/v1/brokers", params=params)
        assert response.status_code == 200, response.text
        found.extend(item["id"] for item in response.json()["items"])
        cursor = response.json()["next_cursor"]
        if cursor is None:
            break
    assert set(found) == expected and len(found) == len(expected)
    for query in ["", "a", "  ", "x" * 101]:
        assert client.get("/api/v1/brokers", params={"q": query}).status_code == 422


def test_public_profile_and_investor_link_flow():
    ctx = context()
    investor, broker = actors(ctx)
    client = TestClient(app_for(ctx))
    profile = client.get(f"/api/v1/brokers/{broker}")
    assert profile.status_code == 200
    assert not {"email", "phone", "license_number", "clients"} & profile.json().keys()
    assert client.get("/api/v1/brokers/suggestions").status_code == 401
    client.cookies.set("access_token", str(investor))
    empty = client.get("/api/v1/broker-links/current")
    assert empty.status_code == 200 and empty.json()["link"] is None
    response = client.post("/api/v1/broker-links", json={"broker_id": str(broker)})
    assert response.status_code == 422 and response.json()["code"] == "CONSENT_REQUIRED"
    response = client.post(
        "/api/v1/broker-links", json={"broker_id": str(broker), "consent_accepted": True}
    )
    assert response.status_code == 201, response.text
    ident = response.json()["id"]
    assert client.post(f"/api/v1/broker-links/{ident}/cancel").json()["status"] == "canceled"
    assert client.get("/api/v1/broker-links?status=canceled").json()["items"][0]["id"] == ident


async def test_investor_proposal_response_and_acceptance_contract():
    ctx, investor, _, _, _, _, proposal = await proposal_fixture()
    client = TestClient(app_for(ctx))
    client.cookies.set("access_token", str(investor))
    detail = client.get(f"/api/v1/proposals/{proposal.id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["versions"][0]["estimated_cost"] == "204.00"
    accepted = client.post(
        f"/api/v1/proposals/{proposal.id}/decision", json={"version": 1, "decision": "accept"}
    )
    assert accepted.status_code == 200 and accepted.json()["accepted_version"] == 1
