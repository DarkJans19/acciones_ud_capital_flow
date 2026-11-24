from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.adapters.outbound.security.passwords import PasswordHasher
from acciones_ud.identity.application.account import AccountService
from acciones_ud.identity.application.account_info import AccountInfoService
from acciones_ud.identity.application.register import RegistrationService
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from tests.identity.test_account_kyc import AccountFake, KycFake
from tests.identity.test_registration_security import payload
from tests.support.clock import FakeClock


class RegistrationFake:
    def __init__(self, account):
        self.account = account
        self.writes = 0

    async def insert(self, user, role):
        self.account.record.update(user)
        self.writes += 1
        return self.account.user_id

    @asynccontextmanager
    async def work(self):
        yield type("Work", (), {"users": self, "interests": self.account})()


def setup(api_settings):
    app, account = create_app(api_settings), AccountFake()
    registration = RegistrationFake(account)
    app.state.registration_service = RegistrationService(
        registration.work, PasswordHasher(), FakeClock()
    )
    app.state.account_service = AccountService(account.work)
    from acciones_ud.identity.adapters.outbound.alpaca.fake_accounts import FakeAlpacaAccounts

    app.state.account_info_service = AccountInfoService(
        account.work, KycFake().work, FakeAlpacaAccounts([])
    )
    current = CurrentUser(
        account.user_id,
        uuid4(),
        "ana@example.com",
        "active",
        False,
        frozenset({"investor"}),
        frozenset({"account:manage"}),
    )
    app.dependency_overrides[get_current_user] = lambda: current
    return TestClient(app), account, registration


def test_public_options_and_registration_edit_round_trip(api_settings):
    client, account, registration = setup(api_settings)
    options = client.get("/api/v1/auth/interest-options")
    assert options.status_code == 200
    assert options.json() == {"markets": ["NASDAQ", "NYSE"], "sectors": ["Technology"]}
    values = ["nyse", "technology", "NYSE"]
    created = client.post("/api/v1/auth/register", json={**payload(), "interests": values})
    assert created.status_code == 201, created.text
    assert registration.writes == 1
    assert account.record["interests"] == ["NYSE", "Technology"]
    for values in (["NYSE", "Technology"], ["NASDAQ"], ["Technology"]):
        result = client.put(
            "/api/v1/users/me/interests", json={"interests": values, "level": "experienced"}
        )
        assert result.status_code == 200, result.text
        assert result.json() == {"interests": values, "level": "experienced"}
        assert client.get("/api/v1/users/me").json()["interests"] == values


@pytest.mark.parametrize("values", [["UnknownMarket"], ["UnknownSector"], ["Tecnología"]])
def test_registration_and_edit_reject_the_same_unknown_values(api_settings, values):
    client, account, registration = setup(api_settings)
    created = client.post("/api/v1/auth/register", json={**payload(), "interests": values})
    edited = client.put(
        "/api/v1/users/me/interests", json={"interests": values, "level": "beginner"}
    )
    assert created.status_code == edited.status_code == 422
    assert account.record["interests"] == []
    assert account.writes == registration.writes == 0


def test_empty_registration_is_allowed_but_empty_replacement_is_not(api_settings):
    client, account, registration = setup(api_settings)
    assert client.post("/api/v1/auth/register", json=payload()).status_code == 201
    result = client.put("/api/v1/users/me/interests", json={"interests": [], "level": "beginner"})
    assert result.status_code == 422 and account.writes == 0 and registration.writes == 1


def test_legacy_interest_is_private_to_its_owner_and_can_be_removed(api_settings):
    client, account, registration = setup(api_settings)
    account.record["interests"] = ["Tecnología"]
    assert client.get("/api/v1/users/me").json()["interests"] == ["Tecnología"]
    result = client.put(
        "/api/v1/users/me/interests",
        json={
            "interests": ["tecnología", "NYSE", "Tecnología"],
            "level": "beginner",
        },
    )
    assert result.status_code == 200
    assert result.json()["interests"] == ["Tecnología", "NYSE"]
    assert "Tecnología" not in str(client.get("/api/v1/auth/interest-options").json())
    assert (
        client.post(
            "/api/v1/auth/register", json={**payload(), "interests": ["Tecnología"]}
        ).status_code
        == 422
    )
    assert registration.writes == 0
    assert (
        client.put(
            "/api/v1/users/me/interests",
            json={
                "interests": ["NYSE"],
                "level": "beginner",
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/users/me/interests",
            json={
                "interests": ["Tecnología"],
                "level": "beginner",
            },
        ).status_code
        == 422
    )
