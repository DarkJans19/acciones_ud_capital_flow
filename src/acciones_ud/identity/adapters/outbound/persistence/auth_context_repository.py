from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.adapters.outbound.persistence.tables import (
    role_assignments as ra,
)
from acciones_ud.identity.adapters.outbound.persistence.tables import (
    role_permissions as rp,
)
from acciones_ud.identity.adapters.outbound.persistence.tables import sessions, users
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.shared.domain.clock import Clock


class AuthContextRepository:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self.session = session
        self.clock = clock

    async def get(self, user_id: UUID, session_id: UUID) -> CurrentUser | None:
        now = self.clock.now()
        query = (
            sa.select(
                users.c.email,
                users.c.account_status,
                users.c.is_premium,
                ra.c.role_code,
                rp.c.permission_code,
            )
            .select_from(
                sessions.join(users, sessions.c.user_id == users.c.id)
                .outerjoin(
                    ra,
                    sa.and_(
                        ra.c.user_id == users.c.id,
                        users.c.account_status == "active",
                        ra.c.status == "ACTIVE",
                        ra.c.valid_from <= now,
                        sa.or_(ra.c.valid_to.is_(None), now < ra.c.valid_to),
                    ),
                )
                .outerjoin(rp, rp.c.role_code == ra.c.role_code)
            )
            .where(
                sessions.c.id == session_id, users.c.id == user_id, sessions.c.revoked_at.is_(None)
            )
        )
        rows = (await self.session.execute(query)).mappings().all()
        if not rows:
            return None
        first = rows[0]
        return CurrentUser(
            user_id,
            session_id,
            first["email"],
            first["account_status"],
            first["is_premium"],
            frozenset(r["role_code"] for r in rows if r["role_code"]),
            frozenset(r["permission_code"] for r in rows if r["permission_code"]),
        )
