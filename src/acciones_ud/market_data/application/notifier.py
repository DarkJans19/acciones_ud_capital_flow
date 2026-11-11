"""Notification dispatch with per-channel isolation (Property 25)."""

from uuid import UUID

from acciones_ud.market_data.domain.entities import Notification, Recipient
from acciones_ud.market_data.domain.notifications import IN_APP, NoDestinationError
from acciones_ud.market_data.domain.ports import (
    ChannelSender,
    NotificationWorkFactory,
)
from acciones_ud.shared.domain.clock import Clock


class Notifier:
    def __init__(
        self,
        uow: NotificationWorkFactory,
        senders: list[ChannelSender],
        clock: Clock,
    ) -> None:
        self.uow = uow
        self.senders = {sender.channel: sender for sender in senders}
        self.clock = clock

    async def notify(
        self,
        recipients: list[Recipient],
        event_type: str,
        payload: dict[str, object],
    ) -> list[Notification]:
        now = self.clock.now()
        created: list[tuple[Notification, Recipient]] = []
        async with self.uow() as work:
            for recipient in recipients:
                notification = await work.notifications.create(
                    recipient.user_id, event_type, payload, now
                )
                for channel in sorted(recipient.channels):
                    await work.notifications.add_delivery(
                        notification.id, channel, "pending"
                    )
                created.append((notification, recipient))
        for notification, recipient in created:
            await self.dispatch(notification, recipient)
        return [notification for notification, _ in created]

    async def dispatch(self, notification: Notification, recipient: Recipient) -> None:
        for channel in sorted(recipient.channels):
            if channel == IN_APP:
                await self._mark(notification.id, channel, "sent", None)
                continue
            sender = self.senders.get(channel)
            if sender is None:
                await self._mark(notification.id, channel, "failed", "sender_unavailable")
                continue
            try:
                await sender.send(recipient, notification)
            except NoDestinationError:
                await self._mark(notification.id, channel, "failed", "no_destination")
            except Exception:
                await self._mark(notification.id, channel, "failed", "sender_error")
            else:
                await self._mark(notification.id, channel, "sent", None)

    async def _mark(
        self,
        notification_id: UUID,
        channel: str,
        status: str,
        error_code: str | None,
    ) -> None:
        async with self.uow() as work:
            await work.notifications.mark_delivery(
                notification_id, channel, status, error_code
            )

    async def list_in_app(self, user_id: UUID, page_size: int) -> list[Notification]:
        async with self.uow() as work:
            return await work.notifications.list_in_app(user_id, page_size)
