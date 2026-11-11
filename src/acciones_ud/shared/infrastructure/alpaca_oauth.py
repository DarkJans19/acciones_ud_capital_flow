"""Broker client-credentials authentication, distinct from legacy Basic keys."""

import asyncio
import time
from collections.abc import AsyncGenerator

import httpx

from acciones_ud.shared.domain.alpaca_errors import AlpacaUnavailable, classify


class BrokerOAuthAuth(httpx.Auth):
    requires_response_body = True

    def __init__(self, auth_url: str, client_id: str, client_secret: str) -> None:
        self.auth_url = auth_url.rstrip("/") + "/v1/oauth2/token"
        self._client_id, self._client_secret = client_id, client_secret
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def async_auth_flow(
        self, request: httpx.Request
    ) -> AsyncGenerator[httpx.Request, httpx.Response]:
        async with self._lock:
            if self._token is None or time.monotonic() >= self._expires_at:
                response = yield httpx.Request(
                    "POST",
                    self.auth_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                    },
                )
                await response.aread()
                if response.status_code != 200:
                    raise classify(response.status_code)
                try:
                    document = response.json()
                    token, ttl = document["access_token"], document["expires_in"]
                    if (
                        not isinstance(token, str)
                        or not token
                        or type(ttl) is not int
                        or ttl <= 0
                        or document.get("token_type", "").lower() != "bearer"
                    ):
                        raise ValueError()
                except (ValueError, KeyError, TypeError, AttributeError):
                    raise AlpacaUnavailable() from None
                self._token = token
                self._expires_at = time.monotonic() + ttl - min(30, ttl / 10)
        request.headers["Authorization"] = "Bearer " + self._token
        response = yield request
        if response.status_code == 401:
            self._expires_at = 0


def build_oauth_client(
    base_url: str, auth_url: str, client_id: str, client_secret: str
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        auth=BrokerOAuthAuth(auth_url, client_id, client_secret),
        timeout=10,
        follow_redirects=False,
    )
