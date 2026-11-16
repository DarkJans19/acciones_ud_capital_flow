from fastapi.testclient import TestClient

from tests.brokers.api.support import app_for
from tests.brokers.support import actors, context
from tests.brokers.unit.test_proposals import proposal_fixture


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
