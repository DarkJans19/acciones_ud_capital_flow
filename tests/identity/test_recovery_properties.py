import hashlib
import secrets
from datetime import timedelta
from uuid import uuid4

from cryptography.fernet import Fernet
from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.identity.adapters.outbound.security.cipher import SecretCipher
from acciones_ud.identity.adapters.outbound.security.passwords import PasswordHasher
from acciones_ud.identity.adapters.outbound.security.tokens import AccessTokenCodec, TokenGenerator
from acciones_ud.identity.adapters.outbound.security.totp import TotpProvider
from acciones_ud.identity.application.login import AuthService
from acciones_ud.identity.domain.recovery_codes import generate_set, hash_set, is_well_formed
from acciones_ud.shared.domain.errors import AppError
from tests.support.clock import FakeClock
from tests.support.identity_fakes import FakeAuthRepository, FakeAuthWorkFactory


# Feature: identity-market-backend, Property 34: Recovery sets are well formed and salted
@given(st.integers(0, 9))
def test_recovery_sets_and_salts(index: int) -> None:
    codes = generate_set()
    assert len(set(codes)) == 10 and all(is_well_formed(code) for code in codes)
    hasher = PasswordHasher()
    encoded = hash_set([codes[index], codes[index]], hasher)
    assert encoded[0] != encoded[1]
    assert all(hasher.verify(codes[index], item) for item in encoded)


class FastTestHasher:
    """State-machine double only; security adapter tests use real Argon2id."""

    def hash(self, password: str) -> str:
        salt = secrets.token_hex(8)
        return salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()

    def verify(self, password: str, encoded: str) -> bool:
        salt, _ = encoded.split(":")
        return encoded == salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()

    def verify_dummy(self, password: str) -> None:
        self.verify(password, self.hash("dummy"))


# Feature: identity-market-backend, Property 35: Recovery consumption follows the reference model
@given(st.lists(st.integers(0, 11), min_size=1, max_size=25))
async def test_recovery_consumption(operations: list[int]) -> None:
    clock = FakeClock()
    hasher = FastTestHasher()
    repo = FakeAuthRepository(
        {
            "id": uuid4(),
            "totp_confirmed_at": clock.now(),
            "account_status": "active",
            "email": "test@example.com",
            "totp_last_step": None,
            "totp_secret_enc": None,
        }
    )
    tokens = TokenGenerator()
    service = AuthService(
        FakeAuthWorkFactory(repo),
        hasher,
        SecretCipher(Fernet.generate_key().decode()),
        AccessTokenCodec("x" * 32, 900, clock),
        tokens,
        TotpProvider(),
        clock,
        604800,
    )
    codes = await service.regenerate(repo.user["id"])
    available = set(codes)
    for action in operations:
        if action == 11:
            old = set(codes)
            codes = await service.regenerate(repo.user["id"])
            available = set(codes)
            assert not old.intersection(available)
            continue
        token = tokens.new()
        await repo.create_challenge(
            repo.user["id"], tokens.digest(token), clock.now() + timedelta(seconds=300)
        )
        code = codes[action] if action < 10 else "INVALID000"
        expected = code in available
        try:
            result = await service.verify(token, None, code, "", "")
        except AppError:
            assert not expected
        else:
            assert expected
            available.remove(code)
            assert result["recovery_codes_remaining"] == len(available)
        assert len(await repo.recovery_hashes(repo.user["id"])) == len(available)
