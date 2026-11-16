from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from acciones_ud.identity import composition
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.adapters.inbound.http.routers.users import router
from acciones_ud.identity.domain.associated_broker import AssociatedBroker
from acciones_ud.identity.domain.models import CurrentUser
from tests.identity.test_account_kyc import AccountFake


def test_users_me_resolves_optional_associated_broker_port(api_settings, monkeypatch):
    account = AccountFake()

    @asynccontextmanager
    async def accounts():
        yield SimpleNamespace(account=account)

    @asynccontextmanager
    async def kyc():
        yield SimpleNamespace(kyc=SimpleNamespace(get=AsyncMock(return_value=None)))

    monkeypatch.setattr(composition, "account_uow", accounts)
    monkeypatch.setattr(composition, "kyc_uow", kyc)
    app = FastAPI()
    app.state.settings, app.state.alpaca_broker = api_settings, None
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        account.user_id, uuid4(), "test@example.com", "active", False, frozenset({"investor"})
    )
    client = TestClient(app)
    assert client.get("/api/v1/users/me").json()["associated_broker"] is None
    broker = AssociatedBroker(
        uuid4(), "Broker Public Name", "Firm", datetime(2026, 11, 16, tzinfo=UTC)
    )
    app.state.associated_broker_reader = SimpleNamespace(
        associated_broker=AsyncMock(return_value=broker)
    )
    response = client.get("/api/v1/users/me")
    assert response.status_code == 200
    assert response.json()["associated_broker"] == {
        "id": str(broker.id),
        "name": broker.name,
        "firm_name": broker.firm_name,
        "since": "2026-11-16T00:00:00Z",
    }
    app.state.associated_broker_reader.associated_broker.assert_awaited_once_with(account.user_id)
