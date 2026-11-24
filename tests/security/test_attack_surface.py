"""RF-02/03, RNF-04: every declared protected HTTP operation fails closed."""

import re

import pytest
from fastapi.testclient import TestClient

from acciones_ud.main import create_app

IDENT = "00000000-0000-0000-0000-000000000001"
PUBLIC = {
    "/health",
    "/api/v1/auth/interest-options",
    "/api/v1/auth/register",
    "/api/v1/auth/register/broker",
    "/api/v1/auth/login",
    "/api/v1/auth/mfa/verify",
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/webhooks/stripe",
    "/api/v1/brokers/{broker_id}",
}


def concrete_path(path: str) -> str:
    return re.sub(
        r"\{([^}]+)\}",
        lambda m: {
            "symbol": "AAPL",
            "code": "NASDAQ",
            "market_code": "NASDAQ",
            "scope": "default",
            "permission_code": "admin:fees",
            "role_code": "administrator",
        }.get(m[1], IDENT),
        path,
    )


@pytest.mark.parametrize("credential", ["missing", "invalid"])
async def test_all_protected_operations_reject_missing_or_invalid_cookie(
    api_settings, credential
):
    import httpx

    app = create_app(api_settings)
    operations = [
        (path, method, operation)
        for path, methods in app.openapi()["paths"].items()
        for method, operation in methods.items()
        if path not in PUBLIC
    ]
    assert operations
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://audit.test"
    ) as client:
        if credential == "invalid":
            client.cookies.set("access_token", "not-a-jwt")
        for path, method, operation in operations:
            assert operation.get("security"), (method, path, "missing OpenAPI security")
            response = await client.request(method, concrete_path(path), json={})
            assert response.status_code == 401, (method, path, response.text)
            assert response.headers.get("x-request-id")
            assert "not-a-jwt" not in response.text


def test_untrusted_cors_origin_cannot_read_credentialed_responses(api_settings):
    client = TestClient(create_app(api_settings))
    response = client.options(
        "/api/v1/users/me",
        headers={
            "Origin": "https://attacker.invalid",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
