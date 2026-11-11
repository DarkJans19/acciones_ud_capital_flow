import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from acciones_ud.identity.domain.models import AccessClaims
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


class AccessTokenCodec:
    def __init__(self, secret: str, ttl: int, clock: Clock) -> None:
        self.secret = secret
        self.ttl = ttl
        self.clock = clock

    def encode(self, user_id: UUID, session_id: UUID) -> str:
        now = self.clock.now()
        return jwt.encode(
            {
                "sub": str(user_id),
                "sid": str(session_id),
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(seconds=self.ttl)).timestamp()),
            },
            self.secret,
            algorithm="HS256",
        )

    def decode(self, token: str) -> AccessClaims:
        try:
            doc = jwt.decode(
                token,
                self.secret,
                algorithms=["HS256"],
                options={
                    "require": ["sub", "sid", "iat", "exp"],
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
            if type(doc["iat"]) is not int or type(doc["exp"]) is not int:
                raise ValueError()
            now = self.clock.now().timestamp()
            if not doc["iat"] <= now < doc["exp"] or doc["exp"] - doc["iat"] > self.ttl:
                raise ValueError()
            return AccessClaims(
                UUID(doc["sub"]),
                UUID(doc["sid"]),
                datetime.fromtimestamp(doc["iat"], UTC),
                datetime.fromtimestamp(doc["exp"], UTC),
            )
        except (jwt.PyJWTError, ValueError, TypeError, OverflowError, OSError):
            raise AppError(401, ErrorCode.NOT_AUTHENTICATED, "Authentication required.") from None


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


class TokenGenerator:
    def new(self) -> str:
        return new_opaque_token()

    def digest(self, token: str) -> bytes:
        return token_hash(token)
