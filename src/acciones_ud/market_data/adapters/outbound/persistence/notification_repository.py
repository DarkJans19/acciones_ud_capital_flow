"""RF-26: stored notifications and per-channel deliveries."""

import json
from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from acciones_ud.market_data.domain.entities import Notification


def _notification(row: Any) -> Notification:
    mapping = cast("dict[str, Any]", row._mapping)
    return Notification(
        id=mapping["id"],
        event_type=str(mapping["event_type"]),
        payload=dict(mapping["payload"] or {}),
        created_at=mapping["created_at"],
    )


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, user_id: UUID, event_type: str, payload: dict[str, object], now: datetime
    ) -> Notification:
        notification_id = uuid4()
        await self.session.execute(
            sa.text(
                "INSERT INTO notifications (id, user_id, event_type, payload, created_at) "
                "VALUES (:id, :user, :event, CAST(:payload AS jsonb), :now)"
            ),
            {
                "id": notification_id,
                "user": user_id,
                "event": event_type,
                "payload": json.dumps(payload),
                "now": now,
            },
        )
        return Notification(
            id=notification_id, event_type=event_type, payload=payload, created_at=now
        )

    async def add_delivery(
        self, notification_id: UUID, channel: str, status: str
    ) -> None:
        await self.session.execute(
            sa.text(
                "INSERT INTO notification_deliveries "
                "(notification_id, channel, status) VALUES (:id, :channel, :status) "
                "ON CONFLICT (notification_id, channel) DO UPDATE SET status = :status"
            ),
            {"id": notification_id, "channel": channel, "status": status},
        )

    async def mark_delivery(
        self,
        notification_id: UUID,
        channel: str,
        status: str,
        error_code: str | None,
    ) -> None:
        await self.session.execute(
            sa.text(
                "UPDATE notification_deliveries SET status = :status, "
                "attempted_at = now(), error_code = :error "
                "WHERE notification_id = :id AND channel = :channel"
            ),
            {
                "id": notification_id,
                "channel": channel,
                "status": status,
                "error": error_code,
            },
        )

    async def list_in_app(self, user_id: UUID, limit: int) -> list[Notification]:
        rows = await self.session.execute(
            sa.text(
                "SELECT id, event_type, payload, created_at FROM notifications "
                "WHERE user_id = :user ORDER BY created_at DESC LIMIT :limit"
            ),
            {"user": user_id, "limit": limit},
        )
        return [_notification(row) for row in rows]
