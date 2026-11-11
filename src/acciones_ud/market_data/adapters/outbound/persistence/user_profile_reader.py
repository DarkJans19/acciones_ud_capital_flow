"""RFP-08: read the user fields the dashboard depends on."""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


class UserProfileReader:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def profile(self, user_id: UUID) -> tuple[list[str], str | None]:
        row = (
            await self.session.execute(
                sa.text(
                    "SELECT interests, investor_level FROM users WHERE id = :user"
                ),
                {"user": user_id},
            )
        ).first()
        if row is None:
            return [], None
        interests = [str(value) for value in (row.interests or [])]
        level = None if row.investor_level is None else str(row.investor_level)
        return interests, level
