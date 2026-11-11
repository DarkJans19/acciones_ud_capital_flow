import re
from datetime import timedelta
from uuid import UUID

from acciones_ud.identity.domain.auth_ports import AuthWorkFactory, Record, TokenGenerator
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.identity.domain.ports import AccessTokenCodec
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


class SessionService:
    def __init__(
        self,
        uow: AuthWorkFactory,
        codec: AccessTokenCodec,
        tokens: TokenGenerator,
        clock: Clock,
        access_ttl: int,
        refresh_ttl: int,
    ) -> None:
        self.uow, self.codec, self.tokens, self.clock = uow, codec, tokens, clock
        self.access_ttl, self.refresh_ttl = access_ttl, refresh_ttl

    async def refresh(self, token: str | None) -> Record:
        if token is None or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            raise AppError(401, ErrorCode.REFRESH_INVALID, "Invalid refresh token.")
        now = self.clock.now()
        refresh = self.tokens.new()
        expires = now + timedelta(seconds=self.refresh_ttl)
        async with self.uow() as work:
            rotated = await work.auth.rotate(
                self.tokens.digest(token), self.tokens.digest(refresh), now, expires
            )
        if rotated is None:
            raise AppError(401, ErrorCode.REFRESH_INVALID, "Invalid refresh token.")
        user_id, sid = rotated
        return {
            "access": self.codec.encode(user_id, sid),
            "refresh": refresh,
            "access_expires_at": now + timedelta(seconds=self.access_ttl),
            "refresh_expires_at": expires,
        }

    async def list(self, user: CurrentUser) -> list[Record]:
        async with self.uow() as work:
            rows = await work.auth.list_sessions(user.user_id, self.clock.now())
        return [
            {
                "session_id": row["id"],
                "user_agent": row["user_agent"],
                "ip_address": row["ip_address"],
                "created_at": row["created_at"],
                "last_used_at": row["last_used_at"],
                "current": row["id"] == user.session_id,
            }
            for row in rows
        ]

    async def close(self, user: CurrentUser, session_id: UUID) -> None:
        async with self.uow() as work:
            found = await work.auth.revoke(user.user_id, session_id, self.clock.now())
        if not found:
            raise AppError(404, ErrorCode.SESSION_NOT_FOUND, "Session not found.")

    async def close_others(self, user: CurrentUser) -> int:
        async with self.uow() as work:
            return await work.auth.revoke_others(user.user_id, user.session_id, self.clock.now())
