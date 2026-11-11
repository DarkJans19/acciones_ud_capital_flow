import logging
from http.cookies import SimpleCookie

import httpx
import pytest
from fastapi import Body
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.config.settings import Settings, require_api_settings
from acciones_ud.main import create_app
from acciones_ud.shared.domain.alpaca_errors import (
    AlpacaAuthError,
    AlpacaNotFound,
    AlpacaRateLimited,
    AlpacaUnavailable,
    AlpacaValidationError,
    classify,
)
from acciones_ud.shared.infrastructure.cookies import clear_auth_cookies, set_auth_cookies
from acciones_ud.shared.infrastructure.logging import SecretRedactionFilter


def test_settings_accept_valid(api_settings: Settings) -> None:
    require_api_settings(api_settings)


# Feature: identity-market-backend, Property 32: Missing configuration is reported by name only
@given(
    st.text(min_size=1),
    st.sampled_from(
        [
            "jwt_secret",
            "alpaca_broker_api_key",
            "alpaca_broker_api_secret",
            "access_token_ttl_seconds",
            "alpaca_data_feed",
            "price_staleness_threshold_seconds",
        ]
    ),
)
def test_bad_config_never_echoes_values(secret: str, field: str) -> None:
    settings = Settings(_env_file=None, **{field: secret})
    with pytest.raises(RuntimeError) as caught:
        require_api_settings(settings)
    message = str(caught.value)
    assert message.startswith("Missing or invalid configuration: ")
    assert all(part.replace("_", "").isupper() for part in message.split(": ")[1].split(", "))


# Feature: identity-market-backend, Property 33: Unexpected errors produce a fixed, safe body
@given(st.text())
def test_unexpected_error_is_safe(secret: str) -> None:
    app = create_app(Settings(_env_file=None))

    @app.get("/fail")
    def fail() -> None:
        raise RuntimeError(secret)

    response = TestClient(app, raise_server_exceptions=False).get("/fail")
    assert response.status_code == 500
    assert response.json() == {
        "code": "INTERNAL_ERROR",
        "message": "An unexpected error occurred.",
        "details": None,
    }
    assert response.headers["x-request-id"]


def test_validation_drops_input() -> None:
    app = create_app(Settings(_env_file=None))

    @app.post("/validate")
    def validate(password: int = Body()) -> int:
        return password

    response = TestClient(app).post("/validate", json="sensitive-password")
    assert response.status_code == 422
    assert "sensitive-password" not in response.text
    assert response.json()["details"]["errors"]


# Feature: identity-market-backend, Property 31: CORS never reflects an unlisted origin
@given(st.from_regex(r"https://[a-z]{1,12}\.test", fullmatch=True))
def test_cors_exact_allowlist(origin: str) -> None:
    app = create_app(Settings(_env_file=None, cors_allowed_origins="https://allowed.test"))
    response = TestClient(app).get("/health", headers={"Origin": origin})
    assert response.headers.get("access-control-allow-origin") == (
        origin if origin == "https://allowed.test" else None
    )


# Feature: identity-market-backend, Property 30: Alpaca error classification
@given(st.integers(min_value=400, max_value=599))
def test_alpaca_classification(status: int) -> None:
    expected = {
        429: AlpacaRateLimited,
        401: AlpacaAuthError,
        403: AlpacaAuthError,
        404: AlpacaNotFound,
        400: AlpacaValidationError,
        409: AlpacaValidationError,
        422: AlpacaValidationError,
    }
    assert isinstance(classify(status), expected.get(status, AlpacaUnavailable))


def test_cookie_attributes(api_settings: Settings) -> None:
    from starlette.responses import Response

    response = Response()
    set_auth_cookies(response, "access", "refresh", api_settings)
    headers = response.headers.getlist("set-cookie")
    assert len(headers) == 2
    cookies = SimpleCookie()
    for header in headers:
        cookies.load(header)
    assert set(cookies) == {"access_token", "refresh_token"}
    for name, path, ttl in (
        ("access_token", "/", "900"),
        ("refresh_token", "/api/v1/auth", "604800"),
    ):
        assert cookies[name]["secure"] and cookies[name]["httponly"]
        assert cookies[name]["samesite"] == "lax"
        assert cookies[name]["path"] == path
        assert cookies[name]["max-age"] == ttl
    response = Response()
    clear_auth_cookies(response, api_settings)
    assert len(response.headers.getlist("set-cookie")) == 2
    assert all("Max-Age=0" in h for h in response.headers.getlist("set-cookie"))


def test_redaction_handles_args_and_exception() -> None:
    record = logging.LogRecord("test", logging.ERROR, "", 1, "secret: %s", ("password",), None)
    assert SecretRedactionFilter(["password"]).filter(record)
    assert record.getMessage() == "secret: ***"


async def test_lifespan_and_health(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/health")
    assert response.json() == {"status": "ok"}


def test_invalid_lifespan_refuses_startup() -> None:
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        with TestClient(create_app(Settings(_env_file=None))):
            pass
