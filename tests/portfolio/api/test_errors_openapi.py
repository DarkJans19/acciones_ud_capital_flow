from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.domain.alpaca_errors import AlpacaRateLimited, AlpacaUnavailable
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.portfolio.api.support import api_for


def authenticated(api_settings):
    app, source, alpaca, repo = api_for(api_settings)
    user = CurrentUser(
        source.account.user_id,
        uuid4(),
        "user@test.co",
        "active",
        False,
        frozenset({"investor", "broker"}),
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app), app, source, alpaca, repo


@pytest.mark.parametrize(
    "error,status,code",
    [
        (AlpacaUnavailable("secret-body"), 502, "ALPACA_UNAVAILABLE"),
        (AlpacaRateLimited("secret-body"), 503, "ALPACA_RATE_LIMITED"),
    ],
)
def test_alpaca_errors_safe_and_failed_report_not_stored(api_settings, caplog, error, status, code):
    client, app, source, alpaca, repo = authenticated(api_settings)
    alpaca.error = error
    for method, route in [("GET", "/positions"), ("POST", "/reports")]:
        response = client.request(
            method, "/api/v1/portfolio" + route, json={"from": "2026-01-01", "to": "2026-01-31"}
        )
        assert response.status_code == status and response.json()["code"] == code
        assert "secret-body" not in response.text and "private-account" not in response.text
    assert not repo.values and "secret-body" not in caplog.text


def test_database_error_and_post_period_validation(api_settings):
    client, app, source, alpaca, repo = authenticated(api_settings)
    response = client.post(
        "/api/v1/portfolio/reports", json={"from": "2026-02-01", "to": "2026-01-01"}
    )
    assert response.status_code == 422 and response.json()["details"]["reason"] == "from_after_to"
    assert not repo.values and alpaca.calls == 0

    async def unavailable(user_id):
        raise AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Database unavailable.")

    source.get = unavailable
    response = client.get("/api/v1/portfolio/positions")
    assert response.status_code == 503 and response.json()["code"] == "DATABASE_UNAVAILABLE"


def test_every_error_response_uses_error_body_and_decimal_schemas(api_settings):
    client, app, source, alpaca, repo = authenticated(api_settings)
    schema = client.get("/openapi.json").json()
    operations = [
        op
        for path, methods in schema["paths"].items()
        if path.startswith("/api/v1/portfolio")
        for op in methods.values()
    ]
    assert len(operations) == 12
    for operation in operations:
        for status, response in operation["responses"].items():
            if int(status) >= 400:
                assert response["content"]["application/json"]["schema"] == {
                    "$ref": "#/components/schemas/ErrorBody"
                }
    position = schema["components"]["schemas"]["PositionResponse"]
    assert position["properties"]["qty"]["type"] == "string"
    assert position["properties"]["market_value"]["format"] == "decimal"
