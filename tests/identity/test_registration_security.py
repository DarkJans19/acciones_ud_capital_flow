from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.schemas.auth import RegisterInvestorIn
from acciones_ud.identity.adapters.outbound.security.passwords import PasswordHasher
from acciones_ud.identity.adapters.outbound.security.tokens import AccessTokenCodec
from acciones_ud.identity.application.register import RegistrationService
from acciones_ud.identity.domain.models import RoleAssignment
from acciones_ud.identity.domain.ports import IdentityUnitOfWork
from acciones_ud.identity.domain.rbac import effective_roles, guard_last_administrator
from acciones_ud.identity.domain.registration import build_new_user
from acciones_ud.identity.domain.validation import normalize_email
from acciones_ud.main import create_app
from acciones_ud.shared.domain.clock import SystemClock
from acciones_ud.shared.domain.errors import AppError


def payload() -> dict[str, object]:
    return {
        "first_names": " Ana ",
        "last_names": "Perez",
        "email": " Ana@example.com ",
        "phone": "+573001234567",
        "country": "co",
        "password": "SafePassword123",
        "terms_accepted": True,
        "monthly_report": False,
        "role": "administrator",
    }


@pytest.mark.parametrize(
    "kind,role,status",
    [
        ("investor", "investor", "active"),
        ("broker", None, "pending_broker_activation"),
        ("administrator", "administrator", "active"),
    ],
)
def test_registration_mapping(kind: str, role: str | None, status: str) -> None:
    user, assignment = build_new_user(
        kind, {**payload(), "firm_name": " Firm ", "license_number": " abc "}
    )
    assert assignment == role
    assert user["account_status"] == status
    assert "password" not in user and "role" not in user
    assert user["email_normalized"] == "ana@example.com"


# Feature: identity-market-backend, Property 2: Email normalization
@given(st.from_regex(r"[a-zA-Z]{1,20}@example\.com", fullmatch=True))
def test_email_normalization(email: str) -> None:
    assert normalize_email("  " + email.upper() + "  ") == normalize_email(email)


# Feature: identity-market-backend, Property 3: Password hashing round trip
@given(st.from_regex(r"[A-Za-z]{8}[0-9]{4}", fullmatch=True))
def test_password_hash(password: str) -> None:
    hasher = PasswordHasher()
    encoded = hasher.hash(password)
    assert encoded.startswith("$argon2id$")
    assert hasher.verify(password, encoded)
    assert not hasher.verify(password + "!", encoded)


# Feature: identity-market-backend, Property 6: Access token codec
@given(st.uuids(), st.uuids(), st.integers(min_value=0, max_value=899))
def test_access_tokens(user: UUID, session: UUID, seconds: int) -> None:
    class Clock:
        instant = datetime(2026, 1, 1, tzinfo=UTC)

        def now(self) -> datetime:
            return self.instant

    clock = Clock()
    codec = AccessTokenCodec("x" * 32, 900, clock)
    token = codec.encode(user, session)
    clock.instant += timedelta(seconds=seconds)
    claims = codec.decode(token)
    assert claims.user_id == user and claims.session_id == session
    with pytest.raises(AppError):
        AccessTokenCodec("y" * 32, 900, clock).decode(token)
    clock.instant = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=900)
    with pytest.raises(AppError):
        codec.decode(token)


# Feature: identity-market-backend, Property 7: Effective roles and permission checks
@given(st.integers(-1000, 1000), st.integers(1, 1000), st.booleans())
def test_effective_roles(offset: int, duration: int, pending: bool) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assignment = RoleAssignment(
        uuid4(),
        uuid4(),
        "investor",
        now + timedelta(seconds=offset),
        now + timedelta(seconds=offset + duration),
    )
    roles = effective_roles([assignment], now, "pending_broker_activation" if pending else "active")
    assert ("investor" in roles) == (not pending and offset <= 0 < offset + duration)


# Feature: identity-market-backend, Property 9: The last administrator cannot be removed
@given(st.integers(min_value=1, max_value=10))
def test_last_admin(count: int) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assignments = [RoleAssignment(uuid4(), uuid4(), "administrator", now) for _ in range(count)]
    users = {a.user_id for a in assignments}
    if count == 1:
        with pytest.raises(AppError, match="last administrator"):
            guard_last_administrator(assignments, assignments[1:], now, users)
    else:
        guard_last_administrator(assignments, assignments[1:], now, users)


@pytest.mark.parametrize("value", [False, "true", 1, None])
def test_terms_are_strict(value: object) -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RegisterInvestorIn.model_validate({**payload(), "terms_accepted": value})


def test_registration_api_uses_safe_response(api_settings: Settings) -> None:
    class Repository:
        records: list[tuple[dict[str, object], str | None]] = []

        async def insert(self, user: dict[str, object], role: str | None) -> UUID:
            self.records.append((user, role))
            return uuid4()

    repository = Repository()

    class Work:
        users = repository

    @asynccontextmanager
    async def uow() -> AsyncIterator[IdentityUnitOfWork]:
        yield Work()

    app = create_app(api_settings)
    app.state.registration_service = RegistrationService(uow, PasswordHasher(), SystemClock())
    client = TestClient(app)
    response = client.post("/api/v1/auth/register", json=payload())
    assert response.status_code == 201
    assert set(response.json()) == {"user_id", "account_status"}
    assert repository.records[0][1] == "investor"
    assert str(repository.records[0][0]["password_hash"]).startswith("$argon2id$")
    assert "password" not in repository.records[0][0]
    response = client.post("/api/v1/auth/register", json={**payload(), "password": "secret"})
    assert response.status_code == 422 and "secret" not in response.text
    assert client.post("/api/v1/admin/users/administrators", json=payload()).status_code == 401
