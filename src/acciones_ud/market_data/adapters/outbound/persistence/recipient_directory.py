"""RF-26: resolve who receives an event and through which channels."""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.market_data.domain.entities import Recipient
from acciones_ud.market_data.domain.notifications import channels_for


class RecipientDirectory:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def recipients(self, event_type: str) -> list[Recipient]:
        return await self._recipients(event_type, None)

    async def recipient(self, user_id: UUID, event_type: str) -> Recipient | None:
        values = await self._recipients(event_type, user_id)
        return next((value for value in values if value.channels), None)

    async def _recipients(self, event_type: str, user_id: UUID | None) -> list[Recipient]:
        rows = (
            await self.session.execute(
                sa.text(
                    "SELECT p.user_id, p.event_type, p.channel, p.enabled, "
                    "u.email, u.telegram_chat_id "
                    "FROM notification_preferences p "
                    "JOIN users u ON u.id = p.user_id "
                    "WHERE p.event_type = :event "
                    + ("AND p.user_id = :user_id" if user_id else "")
                ),
                {"event": event_type, "user_id": user_id},
            )
        ).all()
        by_user: dict[UUID, list[tuple[str, str, bool]]] = {}
        contacts: dict[UUID, tuple[str | None, str | None]] = {}
        for row in rows:
            by_user.setdefault(row.user_id, []).append(
                (str(row.event_type), str(row.channel), bool(row.enabled))
            )
            contacts[row.user_id] = (row.email, row.telegram_chat_id)
        return [
            Recipient(
                user_id=user_id,
                channels=frozenset(channels_for(preferences, event_type)),
                email=contacts[user_id][0],
                telegram_chat_id=contacts[user_id][1],
            )
            for user_id, preferences in by_user.items()
            if any(enabled for _, _, enabled in preferences)
        ]
