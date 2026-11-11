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
        rows = (
            await self.session.execute(
                sa.text(
                    "SELECT user_id, event_type, channel, enabled "
                    "FROM notification_preferences WHERE event_type = :event"
                ),
                {"event": event_type},
            )
        ).all()
        by_user: dict[UUID, list[tuple[str, str, bool]]] = {}
        for row in rows:
            by_user.setdefault(row.user_id, []).append(
                (str(row.event_type), str(row.channel), bool(row.enabled))
            )
        return [
            Recipient(
                user_id=user_id,
                channels=frozenset(channels_for(preferences, event_type)),
            )
            for user_id, preferences in by_user.items()
        ]
