"""Administrative user directory endpoints (25.8, Requirements 20, 21 and 22.3)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.application.user_directory import UserDirectoryService
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.main import create_app
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.support.clock import FakeClock
from tests.support.identity_fakes import FakeDirectoryRepository, FakeDirectoryWorkFactory

NOW = datetime(2026, 1, 1, tzinfo=UTC)
ADMIN = uuid4()


def assignment(role: str, *, status: str = "ACTIVE", days: int = 1) -> dict[str, object]:
    return {
        "role_code": role,
        "status": status,
        "valid_from": NOW - timedelta(days=days),
        "valid_to": None,
    }


def population() -> list[dict[str, object]]:
    return [
        {
            "id": uuid4(),
            "email": "investor@example.com",
            "first_names": "Ana",
            "last_names": "Pérez",
            "phone": None,
            "country": "CO",
            "account_status": "active",
            "is_premium": False,
            "broker_requested": True,
            "created_at": NOW - timedelta(days=3),
            "roles": [assignment("investor")],
            "kyc": None,
        },
        {
            "id": uuid4(),
            "email": "broker@example.com",
            "first_names": "Beto",
            "last_names": "Gómez",
            "phone": "+573001112233",
            "country": "CO",
            "account_status": "pending_broker_activation",
            "is_premium": False,
            "broker_requested": True,
            "created_at": NOW,
            "roles": [assignment("investor")],
            "kyc": {
                "alpaca_account_id": None,
                "status": None,
                "status_updated_at": None,
                "status_checked_at": None,
                "reserved_at": NOW - timedelta(days=1),
                "created_at": NOW - timedelta(days=1),
            },
        },
        {
            "id": uuid4(),
            "email": "linked@example.com",
            "first_names": "Carla",
            "last_names": "Ruiz",
            "phone": None,
            "country": "CO",
            "account_status": "active",
            "is_premium": True,
            "broker_requested": False,
            "created_at": NOW - timedelta(days=1),
            "roles": [assignment("investor"), assignment("broker")],
            "kyc": {
                "alpaca_account_id": "alpaca-account",
                "status": "SUBMITTED",
                "status_updated_at": NOW - timedelta(hours=1),
                "status_checked_at": NOW,
                "reserved_at": NOW - timedelta(days=2),
                "created_at": NOW - timedelta(days=2),
            },
        },
    ]


def make_app(
    settings: Settings,
    users: list[dict[str, object]],
    *,
    roles: frozenset[str] = frozenset({"administrator"}),
    permissions: frozenset[str] = frozenset({"admin:users"}),
    failure: Exception | None = None,
    authenticated: bool = True,
) -> TestClient:
    clock = FakeClock(NOW)
    app = create_app(settings)
    app.state.user_directory_service = UserDirectoryService(
        FakeDirectoryWorkFactory(FakeDirectoryRepository(users, failure)), clock
    )
    if authenticated:
        current = CurrentUser(
            ADMIN, uuid4(), "admin@example.com", "active", False, roles, permissions
        )
        app.dependency_overrides[get_current_user] = lambda: current
    return TestClient(app)


def test_list_returns_page_and_echoes_paging(api_settings: Settings) -> None:
    users = population()
    client = make_app(api_settings, users)

    body = client.get("/api/v1/admin/users", params={"limit": 2, "offset": 1}).json()

    assert body["total"] == 3 and body["limit"] == 2 and body["offset"] == 1
    assert len(body["items"]) == 2
    assert body["items"][0]["email"] == "linked@example.com"
    assert body["items"][0]["kyc_link_state"] == "linked"
    assert body["items"][0]["kyc_status"] == "SUBMITTED"


def test_list_combines_filters(api_settings: Settings) -> None:
    client = make_app(api_settings, population())

    body = client.get(
        "/api/v1/admin/users",
        params={
            "account_status": "active",
            "role": "investor",
            "broker_requested": "true",
            "kyc_link_state": "none",
        },
    ).json()

    assert body["total"] == 1
    assert body["items"][0]["email"] == "investor@example.com"
    assert body["items"][0]["broker_requested"] is True


def test_pending_broker_lists_no_effective_roles(api_settings: Settings) -> None:
    client = make_app(api_settings, population())

    body = client.get(
        "/api/v1/admin/users", params={"account_status": "pending_broker_activation"}
    ).json()

    entry = body["items"][0]
    assert entry["roles"] == []
    assert entry["kyc_link_state"] == "unlinked"
    assert entry["kyc_alpaca_account_id"] is None
    assert entry["kyc_reserved_at"] is not None


def test_detail_returns_the_entry_without_secrets(api_settings: Settings) -> None:
    users = population()
    client = make_app(api_settings, users)
    target = users[2]["id"]

    response = client.get(f"/api/v1/admin/users/{target}")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(target)
    assert body["roles"] == ["broker", "investor"]
    assert body["is_premium"] is True
    text = response.text
    for secret in ("password_hash", "totp_secret_enc", "tax_id_last4"):
        assert secret not in text


def test_unknown_and_malformed_user_ids(api_settings: Settings) -> None:
    client = make_app(api_settings, population())

    assert client.get(f"/api/v1/admin/users/{uuid4()}").status_code == 404
    malformed = client.get("/api/v1/admin/users/not-a-uuid")
    assert malformed.status_code == 422
    assert malformed.json()["code"] == "VALIDATION_ERROR"


def test_unauthenticated_request_wins_over_invalid_parameters(api_settings: Settings) -> None:
    client = make_app(api_settings, population(), authenticated=False)

    response = client.get("/api/v1/admin/users", params={"limit": 0, "q": "  "})

    assert response.status_code == 401


def test_unprivileged_request_wins_over_invalid_parameters(api_settings: Settings) -> None:
    client = make_app(
        api_settings, population(), roles=frozenset({"investor"}), permissions=frozenset()
    )

    response = client.get("/api/v1/admin/users", params={"limit": 0})

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"q": "   "},
        {"q": "x" * 101},
        {"account_status": "deleted"},
        {"role": "auditor"},
        {"broker_requested": "yes"},
        {"kyc_status": "submitted"},
        {"kyc_link_state": "linked "},
    ],
)
def test_invalid_parameters_are_rejected(
    api_settings: Settings, params: dict[str, object]
) -> None:
    client = make_app(api_settings, population())

    response = client.get("/api/v1/admin/users", params=params)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_database_failure_returns_503_without_partial_body(api_settings: Settings) -> None:
    client = make_app(
        api_settings,
        population(),
        failure=AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Database unavailable."),
    )

    response = client.get("/api/v1/admin/users")

    assert response.status_code == 503
    assert response.json() == {
        "code": "DATABASE_UNAVAILABLE",
        "message": "Database unavailable.",
        "details": None,
    }
