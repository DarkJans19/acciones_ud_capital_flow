from uuid import uuid4

from fastapi.testclient import TestClient

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from tests.portfolio.api.support import api_for


def test_routes_and_invalid_period(api_settings):
    app, source, alpaca, repo = api_for(api_settings)
    user = CurrentUser(
        source.account.user_id,
        uuid4(),
        "test@example.com",
        "active",
        False,
        frozenset({"investor", "broker"}),
    )
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    assert client.get("/api/v1/portfolio/positions").json()["totals"]["market_value"] == "0.00"
    params = {"from": "2026-01-01", "to": "2026-01-31"}
    for path in ("executions", "statistics", "risk-profile"):
        assert client.get("/api/v1/portfolio/" + path, params=params).status_code == 200
    response = client.post("/api/v1/portfolio/reports", json=params)
    assert response.status_code == 201
    report = response.json()
    assert report["period"] == params
    assert client.get("/api/v1/portfolio/reports/" + report["id"]).json() == report
    for path in ("executions", "statistics"):
        invalid = client.get(
            "/api/v1/portfolio/" + path, params={"from": "2026-02-01", "to": "2026-01-01"}
        )
        assert invalid.status_code == 422 and invalid.json()["code"] == "INVALID_PERIOD"
    assert client.get("/api/v1/portfolio/reports", params={"page_size": 101}).status_code == 422
    assert client.get("/api/v1/portfolio/reports", params={"cursor": "bad"}).status_code == 422
