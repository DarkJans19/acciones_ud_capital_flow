from datetime import datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.adapters.outbound.persistence import tables as t
from acciones_ud.identity.domain.auth_ports import Record
from acciones_ud.identity.domain.mfa import Challenge


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_user(self, email: str) -> Record | None:
        row = (
            (
                await self.session.execute(
                    sa.select(t.users).where(t.users.c.email_normalized == email)
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    async def lock_user(self, user_id: UUID) -> Record:
        row = (
            (
                await self.session.execute(
                    sa.select(t.users).where(t.users.c.id == user_id).with_for_update()
                )
            )
            .mappings()
            .one()
        )
        return dict(row)

    async def update_user(self, user_id: UUID, changes: Record) -> None:
        await self.session.execute(
            t.users.update().where(t.users.c.id == user_id).values(**changes)
        )

    async def create_challenge(self, user_id: UUID, digest: bytes, expires: datetime) -> None:
        await self.session.execute(
            t.mfa_challenges.insert().values(
                id=uuid4(), user_id=user_id, token_hash=digest, expires_at=expires
            )
        )

    async def lock_challenge(self, digest: bytes) -> Challenge | None:
        row = (
            (
                await self.session.execute(
                    sa.select(t.mfa_challenges)
                    .where(t.mfa_challenges.c.token_hash == digest)
                    .with_for_update()
                )
            )
            .mappings()
            .first()
        )
        if not row:
            return None
        return Challenge(
            row["id"],
            row["user_id"],
            row["expires_at"],
            row["failed_attempts"],
            row["used_at"],
            row["invalidated_at"],
        )

    async def save_challenge(self, challenge: Challenge) -> None:
        await self.session.execute(
            t.mfa_challenges.update()
            .where(t.mfa_challenges.c.id == challenge.id)
            .values(
                failed_attempts=challenge.failed_attempts,
                used_at=challenge.used_at,
                invalidated_at=challenge.invalidated_at,
            )
        )

    async def audit(
        self, user_id: UUID | None, kind: str, result: str, method: str | None, ip: str, agent: str
    ) -> None:
        await self.session.execute(
            t.auth_events.insert().values(
                user_id=user_id,
                kind=kind,
                result=result,
                method=method,
                ip_address=ip,
                user_agent=agent[:512],
            )
        )

    async def recovery_hashes(self, user_id: UUID) -> list[tuple[UUID, str]]:
        rows = (
            await self.session.execute(
                sa.select(t.mfa_recovery_codes.c.id, t.mfa_recovery_codes.c.code_hash).where(
                    t.mfa_recovery_codes.c.user_id == user_id,
                    t.mfa_recovery_codes.c.used_at.is_(None),
                    t.mfa_recovery_codes.c.invalidated_at.is_(None),
                )
            )
        ).all()
        return [(row[0], row[1]) for row in rows]

    async def consume_code(self, code_id: UUID, now: datetime) -> bool:
        result = await self.session.execute(
            t.mfa_recovery_codes.update()
            .where(
                t.mfa_recovery_codes.c.id == code_id,
                t.mfa_recovery_codes.c.used_at.is_(None),
                t.mfa_recovery_codes.c.invalidated_at.is_(None),
            )
            .values(used_at=now)
            .returning(t.mfa_recovery_codes.c.id)
        )
        return result.first() is not None

    async def replace_codes(self, user_id: UUID, hashes: list[str], now: datetime) -> None:
        await self.session.execute(
            t.mfa_recovery_codes.update()
            .where(
                t.mfa_recovery_codes.c.user_id == user_id,
                t.mfa_recovery_codes.c.invalidated_at.is_(None),
            )
            .values(invalidated_at=now)
        )
        set_id = uuid4()
        await self.session.execute(
            t.mfa_recovery_codes.insert(),
            [
                {"id": uuid4(), "user_id": user_id, "set_id": set_id, "code_hash": encoded}
                for encoded in hashes
            ],
        )

    async def create_session(
        self, user_id: UUID, digest: bytes, now: datetime, expires: datetime, ip: str, agent: str
    ) -> UUID:
        session_id = uuid4()
        await self.session.execute(
            t.sessions.insert().values(
                id=session_id,
                user_id=user_id,
                user_agent=agent[:512],
                ip_address=ip,
                last_used_at=now,
            )
        )
        await self._insert_refresh(session_id, digest, expires)
        return session_id

    async def _insert_refresh(self, session_id: UUID, digest: bytes, expires: datetime) -> None:
        await self.session.execute(
            t.refresh_tokens.insert().values(
                id=uuid4(), session_id=session_id, token_hash=digest, expires_at=expires
            )
        )

    async def rotate(
        self, digest: bytes, new_digest: bytes, now: datetime, expires: datetime
    ) -> tuple[UUID, UUID] | None:
        # UPDATE serializes competing rotations. A loser revokes the winner's session too.
        row = (
            await self.session.execute(
                t.refresh_tokens.update()
                .where(
                    t.refresh_tokens.c.token_hash == digest,
                    t.refresh_tokens.c.session_id == t.sessions.c.id,
                    t.refresh_tokens.c.rotated_at.is_(None),
                    t.refresh_tokens.c.expires_at > now,
                    t.sessions.c.revoked_at.is_(None),
                )
                .values(rotated_at=now)
                .returning(t.refresh_tokens.c.session_id)
            )
        ).first()
        if not row:
            sid = (
                await self.session.execute(
                    sa.select(t.refresh_tokens.c.session_id).where(
                        t.refresh_tokens.c.token_hash == digest
                    )
                )
            ).scalar_one_or_none()
            if sid:
                await self.session.execute(
                    t.sessions.update().where(t.sessions.c.id == sid).values(revoked_at=now)
                )
            return None
        session_id: UUID = row[0]
        user_id = (
            await self.session.execute(
                t.sessions.update()
                .where(t.sessions.c.id == session_id)
                .values(last_used_at=now)
                .returning(t.sessions.c.user_id)
            )
        ).scalar_one()
        await self._insert_refresh(session_id, new_digest, expires)
        return user_id, session_id

    async def list_sessions(self, user_id: UUID, now: datetime) -> list[Record]:
        live_refresh = sa.exists(
            sa.select(t.refresh_tokens.c.id).where(
                t.refresh_tokens.c.session_id == t.sessions.c.id,
                t.refresh_tokens.c.rotated_at.is_(None),
                t.refresh_tokens.c.expires_at > now,
            )
        )
        rows = (
            (
                await self.session.execute(
                    sa.select(t.sessions)
                    .where(
                        t.sessions.c.user_id == user_id,
                        t.sessions.c.revoked_at.is_(None),
                        live_refresh,
                    )
                    .order_by(t.sessions.c.last_used_at.desc(), t.sessions.c.id)
                )
            )
            .mappings()
            .all()
        )
        return [dict(row) for row in rows]

    async def revoke(self, user_id: UUID, session_id: UUID, now: datetime) -> bool:
        row = (
            await self.session.execute(
                t.sessions.update()
                .where(
                    t.sessions.c.id == session_id,
                    t.sessions.c.user_id == user_id,
                    t.sessions.c.revoked_at.is_(None),
                )
                .values(revoked_at=now)
                .returning(t.sessions.c.id)
            )
        ).first()
        return row is not None

    async def revoke_others(self, user_id: UUID, session_id: UUID, now: datetime) -> int:
        live_refresh = sa.exists(
            sa.select(t.refresh_tokens.c.id).where(
                t.refresh_tokens.c.session_id == t.sessions.c.id,
                t.refresh_tokens.c.rotated_at.is_(None),
                t.refresh_tokens.c.expires_at > now,
            )
        )
        rows = (
            await self.session.execute(
                t.sessions.update()
                .where(
                    t.sessions.c.user_id == user_id,
                    t.sessions.c.id != session_id,
                    t.sessions.c.revoked_at.is_(None),
                    live_refresh,
                )
                .values(revoked_at=now)
                .returning(t.sessions.c.id)
            )
        ).all()
        return len(rows)
