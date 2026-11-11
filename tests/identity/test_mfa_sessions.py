from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from acciones_ud.config.settings import Settings
from acciones_ud.identity.adapters.inbound.http.schemas.auth import MfaVerifyIn
from acciones_ud.identity.adapters.outbound.security.cipher import SecretCipher
from acciones_ud.identity.adapters.outbound.security.passwords import PasswordHasher
from acciones_ud.identity.adapters.outbound.security.tokens import AccessTokenCodec, TokenGenerator
from acciones_ud.identity.adapters.outbound.security.totp import TotpProvider
from acciones_ud.identity.application.login import AuthService
from acciones_ud.identity.application.sessions import SessionService
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.mfa import Challenge
from acciones_ud.identity.domain.totp_window import match
from acciones_ud.main import create_app
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from tests.support.clock import FakeClock
from tests.support.identity_fakes import FakeAuthRepository, FakeAuthWorkFactory


@pytest.fixture
def auth_setup() -> tuple[AuthService, SessionService, FakeAuthRepository, FakeClock]:
    hasher = PasswordHasher()
    user = {
        "id": uuid4(),
        "email": "ana@example.com",
        "email_normalized": "ana@example.com",
        "password_hash": hasher.hash("Password123"),
        "account_status": "active",
        "totp_secret_enc": None,
        "totp_confirmed_at": None,
        "totp_last_step": None,
    }
    repo = FakeAuthRepository(user)
    clock = FakeClock()
    codec = AccessTokenCodec("x" * 32, 900, clock)
    service = AuthService(
        FakeAuthWorkFactory(repo),
        hasher,
        SecretCipher(Fernet.generate_key().decode()),
        codec,
        TokenGenerator(),
        TotpProvider(),
        clock,
        604800,
    )
    sessions = SessionService(
        FakeAuthWorkFactory(repo), codec, TokenGenerator(), clock, 900, 604800
    )
    return service, sessions, repo, clock


async def enroll(service: AuthService, clock: FakeClock) -> Record:
    login = await service.login(" ANA@EXAMPLE.COM ", "Password123", "127.0.0.1", "test")
    code = service.totp.generator(login["totp_enrollment"]["secret"]).generate(
        int(clock.now().timestamp()) // 30
    )
    return await service.verify(login["mfa_token"], code, None, "127.0.0.1", "test")


async def test_enrollment_recovery_regeneration_and_refresh(auth_setup: tuple) -> None:
    service, sessions, repo, clock = auth_setup
    issued = await enroll(service, clock)
    codes = issued["recovery_codes"]
    assert len(codes) == len(set(codes)) == 10
    assert all(
        encoded.startswith("$argon2id$")
        for _, encoded in await repo.recovery_hashes(repo.user["id"])
    )
    login = await service.login("ana@example.com", "Password123", "", "")
    assert login["totp_enrollment"] is None
    recovered = await service.verify(login["mfa_token"], None, codes[0], "", "")
    assert recovered["recovery_codes_remaining"] == 9 and recovered["recovery_codes"] is None
    another = await service.login("ana@example.com", "Password123", "", "")
    with pytest.raises(AppError):
        await service.verify(another["mfa_token"], None, codes[0], "", "")
    assert repo.challenges[service.tokens.digest(another["mfa_token"])].failed_attempts == 1
    regenerated = await service.regenerate(repo.user["id"])
    assert len(regenerated) == 10 and len(await repo.recovery_hashes(repo.user["id"])) == 10
    with pytest.raises(AppError):
        await service.verify(another["mfa_token"], None, codes[1], "", "")
    rotated = await sessions.refresh(issued["refresh"])
    assert rotated["refresh"] != issued["refresh"]
    sid = service.codec.decode(issued["access"]).session_id
    with pytest.raises(AppError) as caught:
        await sessions.refresh(issued["refresh"])
    assert caught.value.code == ErrorCode.REFRESH_INVALID
    assert repo.sessions[sid]["revoked_at"] is not None
    assert all(code not in str(repo.events) for code in codes + regenerated)


async def test_replayed_totp_and_attempt_limit(auth_setup: tuple) -> None:
    service, _, repo, clock = auth_setup
    await enroll(service, clock)
    secret = service.cipher.decrypt(repo.user["totp_secret_enc"])
    code = service.totp.generator(secret).generate(int(clock.now().timestamp()) // 30)
    login = await service.login("ana@example.com", "Password123", "", "")
    for _ in range(6):
        with pytest.raises(AppError):
            await service.verify(login["mfa_token"], code, None, "", "")
    challenge = repo.challenges[service.tokens.digest(login["mfa_token"])]
    assert challenge.failed_attempts == 5 and challenge.invalidated_at is not None
    assert repo.events[-1]["result"] == "attempt_limit_exceeded"


async def test_wrong_login_and_pending_recovery(auth_setup: tuple) -> None:
    service, _, repo, clock = auth_setup
    for email, password in (("missing@example.com", "Password123"), ("ana@example.com", "wrong")):
        with pytest.raises(AppError) as caught:
            await service.login(email, password, "", "")
        assert caught.value.code == ErrorCode.INVALID_CREDENTIALS
    with pytest.raises(AppError) as caught:
        await service.regenerate(repo.user["id"])
    assert caught.value.code == ErrorCode.MFA_NOT_ENROLLED and not repo.codes
    login = await service.login("ana@example.com", "Password123", "", "")
    with pytest.raises(AppError):
        await service.verify(login["mfa_token"], None, "A" * 10, "", "")
    clock.advance(300)
    with pytest.raises(AppError):
        await service.verify(login["mfa_token"], "123456", None, "", "")
    assert not repo.sessions


# Feature: identity-market-backend, Property 4: TOTP window and replay protection
@given(st.integers(1_000_000, 5_000_000), st.integers(-5, 5), st.integers(-5, 5))
def test_totp_window(step: int, offset: int, last_offset: int) -> None:
    class Generator:
        def generate(self, value: int) -> str:
            return str(value % 1_000_000).zfill(6)

    generator = Generator()
    now = datetime.fromtimestamp(step * 30, UTC)
    matched = match(generator, generator.generate(step + offset), now, step + last_offset)
    assert matched == (step + offset if abs(offset) <= 1 and offset > last_offset else None)
    assert match(generator, "１２３４５６", now, None) is None


# Feature: identity-market-backend, Property 5: MFA challenge attempt limit and single use
@given(st.lists(st.booleans(), min_size=1, max_size=30))
def test_challenge_state(attempts: list[bool]) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    challenge = Challenge(uuid4(), uuid4(), now + timedelta(seconds=300))
    failures, used = 0, False
    for valid in attempts:
        expected = not used and failures < 5
        assert challenge.usable(now) == expected
        if expected:
            if valid:
                assert challenge.succeed(now)
                used = True
            else:
                challenge.fail(now)
                failures += 1
    assert not challenge.usable(now + timedelta(seconds=300))


# Feature: identity-market-backend, Property 36: MFA verification input validation
@given(st.one_of(st.none(), st.text(max_size=12)), st.one_of(st.none(), st.text(max_size=12)))
def test_mfa_input(code: str | None, recovery: str | None) -> None:
    import re

    valid = (
        code is not None and re.fullmatch(r"[0-9]{6}", code) is not None and recovery is None
    ) or (
        code is None
        and recovery is not None
        and re.fullmatch(r"[A-Z0-9]{10}", recovery.strip().upper()) is not None
    )
    if valid:
        MfaVerifyIn(mfa_token="token", code=code, recovery_code=recovery)
    else:
        with pytest.raises(ValidationError):
            MfaVerifyIn(mfa_token="token", code=code, recovery_code=recovery)


def test_mfa_http_cookies_and_safe_response(
    auth_setup: tuple, api_settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    service, sessions, repo, clock = auth_setup
    app = create_app(api_settings)
    app.state.auth_service = service
    app.state.session_service = sessions
    client = TestClient(app, base_url="https://api.test")
    login = client.post(
        "/api/v1/auth/login", json={"email": "ana@example.com", "password": "Password123"}
    )
    assert login.status_code == 200 and "set-cookie" not in login.headers
    body = login.json()
    generator = service.totp.generator(body["totp_enrollment"]["secret"])
    code = generator.generate(int(clock.now().timestamp()) // 30)
    invalid = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": body["mfa_token"]})
    assert invalid.status_code == 422
    assert repo.challenges[service.tokens.digest(body["mfa_token"])].failed_attempts == 0
    verify = client.post(
        "/api/v1/auth/mfa/verify", json={"mfa_token": body["mfa_token"], "code": code}
    )
    assert verify.status_code == 200 and "access" not in verify.json()
    assert code not in caplog.text
    assert all(value not in caplog.text for value in verify.json()["recovery_codes"])
    assert len(verify.headers.get_list("set-cookie")) == 2
    assert all("Secure" in x and "HttpOnly" in x for x in verify.headers.get_list("set-cookie"))
    old_refresh = client.cookies.get("refresh_token")
    assert client.post("/api/v1/auth/refresh").status_code == 200
    client.cookies.set("refresh_token", old_refresh, domain="api.test", path="/api/v1/auth")
    failed = client.post("/api/v1/auth/refresh")
    assert failed.status_code == 401 and len(failed.headers.get_list("set-cookie")) == 2
