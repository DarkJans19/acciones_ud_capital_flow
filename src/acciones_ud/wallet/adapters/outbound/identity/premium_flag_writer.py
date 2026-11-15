from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.identity.adapters.outbound.persistence.tables import users


class PremiumFlagAdapter:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def set_premium(self, user_id: UUID, value: bool) -> None:
        await self.session.execute(
            sa.update(users).where(users.c.id == user_id).values(is_premium=value)
        )
