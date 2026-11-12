from contextlib import AbstractAsyncContextManager
from typing import Protocol
from uuid import UUID

from acciones_ud.identity.domain.audit import AuditEntry
from acciones_ud.identity.domain.models import AccessClaims, CurrentUser


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, encoded: str) -> bool: ...
    def verify_dummy(self, password: str) -> None: ...


class AccessTokenCodec(Protocol):
    def encode(self, user_id: UUID, session_id: UUID) -> str: ...
    def decode(self, token: str) -> AccessClaims: ...


class SecretCipher(Protocol):
    def encrypt(self, plaintext: str) -> str: ...
    def decrypt(self, ciphertext: str) -> str: ...


class TotpGenerator(Protocol):
    def generate(self, step: int) -> str: ...


class AuthContextRepository(Protocol):
    async def get(self, user_id: UUID, session_id: UUID) -> CurrentUser | None: ...


class UserRepository(Protocol):
    async def insert(self, user: dict[str, object], role: str | None) -> UUID: ...


class AuditRepository(Protocol):
    async def append(self, entry: AuditEntry) -> None: ...


class IdentityUnitOfWork(Protocol):
    @property
    def users(self) -> UserRepository: ...

    @property
    def audit(self) -> AuditRepository: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[IdentityUnitOfWork]: ...
