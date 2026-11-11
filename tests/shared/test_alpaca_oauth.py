import asyncio

import httpx
import pytest

from acciones_ud.config.settings import Settings, require_api_settings
from acciones_ud.shared.domain.alpaca_errors import (
    AlpacaAuthError,
    AlpacaRateLimited,
    AlpacaUnavailable,
)
from acciones_ud.shared.infrastructure.alpaca_oauth import BrokerOAuthAuth


async def test_oauth_is_distinct_from_basic_and_serializes_token_refresh() -> None:
    tokens, calls = [], []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/oauth2/token":
            tokens.append(request)
            assert request.url.host == "authx.sandbox.alpaca.markets"
            assert b"grant_type=client_credentials" in request.content
            return httpx.Response(
                200,
                json={"access_token": "private-token", "expires_in": 899, "token_type": "Bearer"},
            )
        calls.append(request)
        assert request.headers["authorization"] == "Bearer private-token"
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(
        base_url="https://broker-api.sandbox.alpaca.markets",
        auth=BrokerOAuthAuth("https://authx.sandbox.alpaca.markets", "client", "secret"),
        transport=httpx.MockTransport(handler),
    ) as client:
        await asyncio.gather(*(client.get("/v1/clock") for _ in range(5)))
    assert len(tokens) == 1 and len(calls) == 5


async def test_bad_oauth_token_never_reaches_broker() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(401, json={"message": "secret details"})

    async with httpx.AsyncClient(
        base_url="https://broker-api.sandbox.alpaca.markets",
        auth=BrokerOAuthAuth("https://authx.sandbox.alpaca.markets", "client", "secret"),
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(AlpacaAuthError):
            await client.get("/v1/accounts")
    assert len(calls) == 1


@pytest.mark.parametrize("status,error", [(429, AlpacaRateLimited), (503, AlpacaUnavailable)])
async def test_oauth_provider_failures_are_classified_without_retry(
    status: int, error: type[Exception]
) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, json={"private": "details"})

    async with httpx.AsyncClient(
        base_url="https://broker-api.sandbox.alpaca.markets",
        auth=BrokerOAuthAuth("https://authx.sandbox.alpaca.markets", "client", "secret"),
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(error):
            await client.get("/v1/accounts")
    assert len(calls) == 1


def test_legacy_names_are_explicit_and_oauth_does_not_need_basic(api_settings: Settings) -> None:
    values = api_settings.model_dump()
    values.update(
        database_url=None,
        migration_database_url=None,
        database_connection="postgresql://test:test@localhost/test?sslmode=require",
        alpaca_broker_api_key=None,
        alpaca_broker_api_secret=None,
        client_id="client",
        client_secret="secret",
        alpaca_auth_url="https://authx.sandbox.alpaca.markets",
    )
    settings = Settings(**values)
    require_api_settings(settings)
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert "sslmode" not in settings.database_url
