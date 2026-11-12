from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.config.settings import Settings
from acciones_ud.identity import composition
from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.adapters.inbound.http.schemas.admin import AssignmentIn
from acciones_ud.identity.adapters.outbound.security.tokens import AccessTokenCodec
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.identity.domain.validation import invalid_registration_fields
from acciones_ud.main import create_app
from acciones_ud.shared.domain.clock import SystemClock
from acciones_ud.shared.domain.errors import AppError
from tests.identity.test_registration_security import payload


# Feature: identity-market-backend, Property 1: Registration validation
@given(
    st.sets(
        st.sampled_from(
            [
                "first_names",
                "last_names",
                "email",
                "phone",
                "country",
                "password",
                "terms_accepted",
                "monthly_report",
            ]
        )
    )
)
def test_registration_fields(fields: set[str]) -> None:
    body = payload()
    for name in fields:
        body.pop(name)
    assert set(invalid_registration_fields(body, "investor")) == fields


# Feature: identity-market-backend, Property 8: Role assignment validity validation
@given(st.integers(-100, 100), st.booleans())
def test_validity(offset: int, aware: bool) -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC if aware else None)
    end = start + timedelta(seconds=offset)
    if aware and offset > 0:
        AssignmentIn(valid_from=start, valid_to=end)
    else:
        with pytest.raises((ValueError, AppError)):
            AssignmentIn(valid_from=start, valid_to=end)


def test_authentication_rejects_missing_bad_expired_and_revoked(
    api_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(api_settings)
    client = TestClient(app, base_url="https://api.test")
    uid, sid = uuid4(), uuid4()
    assert client.get("/api/v1/users/me").status_code == 401
    client.cookies.set("access_token", "broken")
    assert client.get("/api/v1/users/me").status_code == 401

    class Clock:
        def now(self) -> datetime:
            return datetime(2020, 1, 1, tzinfo=UTC)

    client.cookies.set("access_token", AccessTokenCodec("x" * 32, 900, Clock()).encode(uid, sid))
    assert client.get("/api/v1/users/me").status_code == 401
    token = AccessTokenCodec("x" * 32, 900, SystemClock()).encode(uid, sid)
    client.cookies.set("access_token", token)

    async def revoked(request: Request, user_id: object, session_id: object) -> None:
        return None

    monkeypatch.setattr(composition, "auth_context", revoked)
    assert client.get("/api/v1/users/me").status_code == 401


def test_pending_broker_and_no_permission_cannot_modify(api_settings: Settings) -> None:
    app = create_app(api_settings)
    current = CurrentUser(
        uuid4(),
        uuid4(),
        "ana@example.com",
        "pending_broker_activation",
        False,
        frozenset({"broker"}),
        frozenset({"account:manage"}),
    )
    app.dependency_overrides[get_current_user] = lambda: current
    client = TestClient(app)
    response = client.get("/api/v1/users/preferences/orders")
    assert response.status_code == 403 and response.json()["code"] == "FORBIDDEN"
    assert client.post("/api/v1/admin/users/administrators", json=payload()).status_code == 403
    response = client.put(f"/api/v1/admin/users/{uuid4()}/premium", json={"is_premium": True})
    assert response.status_code == 403


def test_administrator_input_and_privileged_assignment_guard(api_settings: Settings) -> None:
    app = create_app(api_settings)
    current = CurrentUser(
        uuid4(),
        uuid4(),
        "ana@example.com",
        "active",
        False,
        frozenset({"investor"}),
        frozenset({"admin:users", "admin:rbac"}),
    )
    app.dependency_overrides[get_current_user] = lambda: current
    client = TestClient(app)
    assert client.post("/api/v1/admin/users/administrators", json=payload()).status_code == 403
    assert client.post(f"/api/v1/admin/users/{uuid4()}/broker-activation").status_code == 403
    assert (
        client.post(
            f"/api/v1/admin/users/{uuid4()}/roles",
            json={"role": "administrator", "valid_from": "2026-01-01T00:00:00Z"},
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/v1/admin/users/{uuid4()}/premium", json={"is_premium": "true"}
        ).status_code
        == 422
    )


def test_openapi_errors_and_public_docs(api_settings: Settings) -> None:
    client = TestClient(create_app(api_settings))
    assert client.get("/docs").status_code == 200
    document = client.get("/openapi.json").json()
    assert "ErrorBody" in document["components"]["schemas"]
    assert document["components"]["securitySchemes"]["AccessTokenCookie"]["in"] == "cookie"
    assert document["paths"]["/api/v1/users/me"]["get"]["security"] == [{"AccessTokenCookie": []}]
    assert document["paths"]["/api/v1/auth/refresh"]["post"]["security"] == [
        {"RefreshTokenCookie": []}
    ]
    for path, methods in document["paths"].items():
        if path == "/health":
            continue
        for method, operation in methods.items():
            responses = operation["responses"]
            for status, response in responses.items():
                if int(status) >= 400:
                    assert response["content"]["application/json"]["schema"]["$ref"].endswith(
                        "/ErrorBody"
                    )
            if path not in {
                "/api/v1/auth/register",
                "/api/v1/auth/register/broker",
                "/api/v1/auth/login",
                "/api/v1/auth/mfa/verify",
                "/api/v1/auth/logout",
            }:
                assert "401" in responses
            if method in {"put", "post"} and operation.get("requestBody"):
                assert "422" in responses
    assert api_settings.jwt_secret.get_secret_value() not in str(document)
