"""Property 44: logout always clears both cookies and revokes exactly one Session.

Requirement 4 criteria 6, 11, 12, 13 and 14 (decision D10, gap C1). The reference
model below is written independently of ``identity.domain.logout``.
"""

import asyncio
from uuid import UUID, uuid4

import httpx
from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.outbound.security.tokens import (
    AccessTokenCodec,
    TokenGenerator,
    new_opaque_token,
)
from acciones_ud.identity.application.sessions import SessionService
from acciones_ud.main import create_app
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.support.clock import FakeClock
from tests.support.identity_fakes import FakeAuthRepository, FakeAuthWorkFactory

USER = uuid4()
OTHER = uuid4()
ACCESS_TTL = 900
REFRESH_TTL = 604800


def make_repo(user_id: UUID) -> FakeAuthRepository:
    return FakeAuthRepository(
        {
            "id": user_id,
            "email": "ana@example.com",
            "email_normalized": "ana@example.com",
            "password_hash": "$argon2id$stub",
            "account_status": "active",
            "totp_secret_enc": None,
            "totp_confirmed_at": None,
            "totp_last_step": None,
        }
    )


async def make_services(
    failure: Exception | None = None,
) -> tuple[SessionService, FakeAuthRepository, FakeClock, AccessTokenCodec, FakeAuthWorkFactory]:
    clock = FakeClock()
    repo = make_repo(USER)
    factory = FakeAuthWorkFactory(repo, failure)
    codec = AccessTokenCodec("x" * 32, ACCESS_TTL, clock)
    service = SessionService(factory, codec, TokenGenerator(), clock, ACCESS_TTL, REFRESH_TTL)
    return service, repo, clock, codec, factory


async def seed_sessions(
    repo: FakeAuthRepository, clock: FakeClock
) -> tuple[UUID, UUID, str, str]:
    tokens = TokenGenerator()
    refresh_a, refresh_b = tokens.new(), tokens.new()
    session_a = await repo.create_session(
        USER, tokens.digest(refresh_a), clock.now(), clock.now(), "127.0.0.1", "test"
    )
    session_b = await repo.create_session(
        OTHER, tokens.digest(refresh_b), clock.now(), clock.now(), "127.0.0.1", "test"
    )
    return session_a, session_b, refresh_a, refresh_b


def client_for(settings: Settings, service: SessionService) -> httpx.AsyncClient:
    app = create_app(settings)
    app.state.session_service = service
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.test")


def cookie_header(access: str | None, refresh: str | None) -> dict[str, str]:
    pairs = [
        f"{name}={value}"
        for name, value in (("access_token", access), ("refresh_token", refresh))
        if value is not None
    ]
    return {"cookie": "; ".join(pairs)} if pairs else {}


# Feature: identity-market-backend, Property 44: Logout always clears both cookies and
# revokes exactly the reference Session
@given(
    access=st.sampled_from(["none", "active", "session_revoked", "expired"]),
    refresh=st.sampled_from(["none", "a", "b", "rotated_a", "expired_b", "unknown"]),
)
def test_logout_revokes_exactly_the_reference_session(access: str, refresh: str) -> None:
    # Function-scoped fixtures are not reset between generated inputs, so the
    # settings used by this property are built inside the test.
    settings = Settings(_env_file=None, app_env="test")
    asyncio.run(_logout_scenario(settings, access, refresh))


async def _logout_scenario(api_settings: Settings, access: str, refresh: str) -> None:
    service, repo, clock, codec, _ = await make_services()
    session_a, session_b, refresh_a, refresh_b = await seed_sessions(repo, clock)
    tokens = TokenGenerator()
    revoked_before: set[UUID] = set()

    access_value = codec.encode(USER, session_a)
    if access == "none":
        access_value = None
    elif access == "session_revoked":
        repo.sessions[session_a]["revoked_at"] = clock.now()
        revoked_before.add(session_a)
    elif access == "expired":
        clock.advance(ACCESS_TTL + 1)

    refresh_value: str | None
    if refresh == "none":
        refresh_value = None
    elif refresh == "a":
        refresh_value = refresh_a
    elif refresh == "b":
        refresh_value = refresh_b
    elif refresh == "rotated_a":
        repo.refreshes[tokens.digest(refresh_a)]["rotated"] = True
        refresh_value = refresh_a
    elif refresh == "expired_b":
        repo.refreshes[tokens.digest(refresh_b)]["expires"] = clock.now()
        refresh_value = refresh_b
    else:
        refresh_value = new_opaque_token()

    # Reference model, independent of the implementation under test.
    access_effective = access == "active"
    if access_effective:
        expected: UUID | None = session_a
    elif refresh in {"a", "rotated_a"}:
        expected = session_a
    elif refresh in {"b", "expired_b"}:
        expected = session_b
    else:
        expected = None

    async with client_for(api_settings, service) as client:
        response = await client.post(
            "/api/v1/auth/logout", headers=cookie_header(access_value, refresh_value)
        )

    assert response.status_code == 204
    cleared = response.headers.get_list("set-cookie")
    assert len(cleared) == 2
    assert all("Max-Age=0" in header for header in cleared)
    assert {header.split("=")[0] for header in cleared} == {"access_token", "refresh_token"}

    for session_id in (session_a, session_b):
        if session_id == expected:
            assert repo.sessions[session_id]["revoked_at"] is not None
        elif session_id in revoked_before:
            assert repo.sessions[session_id]["revoked_at"] is not None
        else:
            assert repo.sessions[session_id]["revoked_at"] is None


async def test_logout_revokes_a_rotated_refresh_token_session(
    api_settings: Settings,
) -> None:
    service, repo, clock, codec, _ = await make_services()
    session_a, _, refresh_a, _ = await seed_sessions(repo, clock)
    repo.refreshes[TokenGenerator().digest(refresh_a)]["rotated"] = True

    async with client_for(api_settings, service) as client:
        response = await client.post(
            "/api/v1/auth/logout", headers=cookie_header(None, refresh_a)
        )

    assert response.status_code == 204
    assert repo.sessions[session_a]["revoked_at"] is not None


async def test_logout_database_failure_clears_cookies_and_changes_nothing(
    api_settings: Settings,
) -> None:
    service, repo, clock, codec, _ = await make_services(
        AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Database unavailable.")
    )
    session_a, _, refresh_a, _ = await seed_sessions(repo, clock)

    async with client_for(api_settings, service) as client:
        response = await client.post(
            "/api/v1/auth/logout", headers=cookie_header(codec.encode(USER, session_a), refresh_a)
        )

    assert response.status_code == 503
    assert response.json()["code"] == "DATABASE_UNAVAILABLE"
    cleared = response.headers.get_list("set-cookie")
    assert len(cleared) == 2
    assert all("Max-Age=0" in header for header in cleared)
    assert repo.sessions[session_a]["revoked_at"] is None


async def test_refresh_after_logout_is_rejected(api_settings: Settings) -> None:
    service, repo, clock, codec, _ = await make_services()
    session_a, _, refresh_a, _ = await seed_sessions(repo, clock)

    async with client_for(api_settings, service) as client:
        logout = await client.post(
            "/api/v1/auth/logout", headers=cookie_header(codec.encode(USER, session_a), refresh_a)
        )
        assert logout.status_code == 204
        refreshed = await client.post(
            "/api/v1/auth/refresh", headers=cookie_header(None, refresh_a)
        )

    assert refreshed.status_code == 401
    assert refreshed.json()["code"] == "REFRESH_INVALID"
    assert repo.sessions[session_a]["revoked_at"] is not None


async def test_logout_without_credentials_is_204_and_changes_nothing(
    api_settings: Settings,
) -> None:
    service, repo, clock, _, _ = await make_services()
    await seed_sessions(repo, clock)

    async with client_for(api_settings, service) as client:
        response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert len(response.headers.get_list("set-cookie")) == 2
    assert all(session["revoked_at"] is None for session in repo.sessions.values())
