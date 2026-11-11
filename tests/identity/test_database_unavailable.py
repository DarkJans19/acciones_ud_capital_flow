import importlib
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from acciones_ud.config import settings as config
from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from tests.identity.test_financial_profile import kyc_payload
from tests.identity.test_registration_security import payload


async def test_closed_database_returns_safe_503(
    api_settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # This is always a closed local endpoint, never an environment/developer connection.
    monkeypatch.setattr(config, "get_settings", lambda: api_settings)
    db = importlib.import_module("acciones_ud.shared.infrastructure.db")
    engine = db.build_engine("postgresql+asyncpg://test:test@127.0.0.1:1/disposable")
    monkeypatch.setattr(db, "session_factory", async_sessionmaker(engine, expire_on_commit=False))
    app = create_app(api_settings)
    current = CurrentUser(
        uuid4(),
        uuid4(),
        "ana@example.com",
        "active",
        False,
        frozenset({"investor"}),
        frozenset({"account:manage", "kyc:submit"}),
    )
    app.dependency_overrides[get_current_user] = lambda: current
    provider_calls = []

    def provider(request: httpx.Request) -> httpx.Response:
        provider_calls.append(request)
        return httpx.Response(500)

    broker = httpx.AsyncClient(
        base_url="https://sandbox.test", transport=httpx.MockTransport(provider)
    )
    app.state.alpaca_broker = broker
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://api.test"
        ) as client:
            for path, body in (
                ("/api/v1/auth/register", payload()),
                ("/api/v1/auth/login", {"email": "ana@example.com", "password": "Password123"}),
            ):
                response = await client.post(path, json=body)
                assert response.status_code == 503
                assert response.json()["code"] == "DATABASE_UNAVAILABLE"
                assert "test:test" not in response.text and "Password123" not in response.text
            response = await client.put(
                "/api/v1/users/preferences/orders",
                json={
                    "default_order_type": "market",
                    "daily_order_limit": 50,
                    "high_order_threshold_usd": "10000",
                    "extra_confirmation": True,
                },
            )
            assert response.status_code == 503
            assert response.json()["code"] == "DATABASE_UNAVAILABLE"
            response = await client.post("/api/v1/kyc/account", json=kyc_payload())
            assert response.status_code == 503
            assert response.json()["code"] == "DATABASE_UNAVAILABLE"
            assert provider_calls == []
    finally:
        await broker.aclose()
        await engine.dispose()
