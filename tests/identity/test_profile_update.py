from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.adapters.outbound.alpaca.fake_accounts import FakeAlpacaAccounts
from acciones_ud.identity.application.account import AccountService
from acciones_ud.identity.application.account_info import AccountInfoService
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.identity.domain.profile import normalize_profile_patch
from acciones_ud.main import create_app
from acciones_ud.shared.domain.errors import AppError
from tests.identity.test_account_kyc import AccountFake, KycFake


def setup(api_settings, *, status="active", kyc=None):
    app, repo, alpaca = create_app(api_settings), AccountFake(), FakeAlpacaAccounts([])
    repo.record["account_status"] = status
    current = CurrentUser(repo.user_id, uuid4(), "ana@example.com", status, False)
    app.dependency_overrides[get_current_user] = lambda: current
    app.state.account_service = AccountService(repo.work)
    app.state.account_info_service = AccountInfoService(repo.work, KycFake(kyc).work, alpaca)

    async def has_kyc(user_id):
        assert user_id == repo.user_id
        return kyc is not None

    repo.has_kyc = has_kyc
    return TestClient(app), repo, alpaca


@pytest.mark.parametrize("status", ["active", "pending_broker_activation"])
def test_partial_update_and_get_preserve_omitted_and_protected_fields(api_settings, status):
    client, repo, alpaca = setup(api_settings, status=status)
    before = deepcopy(repo.record)
    response = client.patch("/api/v1/users/me", json={"first_names": " María Ana "})
    assert response.status_code == 200, response.text
    assert response.json() == {
        "first_names": "María Ana",
        "last_names": "Perez",
        "phone": "+573001234567",
        "country": "CO",
    }
    assert repo.record == {**before, "first_names": "María Ana"}
    assert (client.get("/api/v1/users/me")).json()["first_names"] == "María Ana"
    response = client.patch(
        "/api/v1/users/me",
        json={
            "last_names": " López ",
            "phone": "+15555550123",
            "country": "us",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "first_names": "María Ana",
        "last_names": "López",
        "phone": "+15555550123",
        "country": "US",
    }
    profile = client.get("/api/v1/users/me").json()
    assert all(profile[k] == v for k, v in response.json().items())
    assert repo.writes == 2 and alpaca.calls == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"first_names": None},
        {"last_names": None},
        {"phone": None},
        {"country": None},
        {"first_names": ""},
        {"first_names": "   "},
        {"last_names": "x" * 101},
        {"phone": "3001234567"},
        {"phone": "+0123456789"},
        {"country": "COL"},
        {"country": "ZZ"},
        {"first_names": 23},
        {"user_id": str(uuid4())},
        {"id": str(uuid4())},
        {"roles": ["administrator"]},
        {"permissions": ["admin:rbac"]},
        {"account_status": "active"},
        {"password": "Change123"},
        {"totp_secret_enc": "unsafe"},
        {"is_premium": True},
        {"kyc_status": "ACTIVE"},
        {"alpaca_account_id": "foreign"},
        {"tax_id": "849261395"},
        {"email": "other@example.com"},
        {"first_names": "Valid", "roles": ["administrator"]},
    ],
)
def test_invalid_or_protected_fields_are_atomic(api_settings, body):
    client, repo, alpaca = setup(api_settings)
    before = deepcopy(repo.record)
    result = client.patch("/api/v1/users/me", json=body)
    assert result.status_code == 422, result.text
    assert result.json()["code"] == "VALIDATION_ERROR"
    assert repo.record == before and repo.writes == 0 and alpaca.calls == []


@pytest.mark.parametrize(
    "kyc",
    [
        {"alpaca_account_id": None, "status": None},
        {"alpaca_account_id": "test-account", "status": "SUBMITTED"},
        {"alpaca_account_id": "test-account", "status": "APPROVED"},
        {"alpaca_account_id": "test-account", "status": "ACTIVE"},
        {"alpaca_account_id": "test-account", "status": "REJECTED"},
        {"alpaca_account_id": "test-account", "status": "ACCOUNT_CLOSED"},
    ],
)
def test_any_kyc_reservation_or_link_blocks_personal_edits(api_settings, kyc):
    client, repo, alpaca = setup(api_settings, kyc=kyc)
    before = deepcopy(repo.record)
    result = client.patch("/api/v1/users/me", json={"phone": "+15555550123"})
    assert result.status_code == 409
    assert result.json()["code"] == "PROFILE_KYC_LOCKED"
    assert repo.record == before and repo.writes == 0 and alpaca.calls == []


def test_profile_requires_authentication(api_settings):
    client = TestClient(create_app(api_settings))
    assert client.patch("/api/v1/users/me", json={"first_names": "Ana"}).status_code == 401
    assert client.patch("/api/v1/users/me", json={}).status_code == 401


async def test_application_enforces_allowlist_without_http():
    repo = AccountFake()
    with pytest.raises(AppError):
        await AccountService(repo.work).update_profile(repo.user_id, {"roles": ["administrator"]})
    assert repo.writes == 0
    assert normalize_profile_patch({"first_names": " Ana ", "country": "co"}) == {
        "first_names": "Ana",
        "country": "CO",
    }


def test_openapi_profile_and_catalog_contract(api_settings):
    document = TestClient(create_app(api_settings)).get("/openapi.json").json()
    operation = document["paths"]["/api/v1/users/me"]["patch"]
    assert operation["security"] == [{"AccessTokenCookie": []}]
    assert {"200", "401", "409", "422", "503"} <= operation["responses"].keys()
    schema = document["components"]["schemas"]["ProfilePatchIn"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"first_names", "last_names", "phone", "country"}
    assert schema.get("required", []) == []
    for field in schema["properties"].values():
        assert field["type"] == "string"
    assert "security" not in document["paths"]["/api/v1/auth/interest-options"]["get"]
