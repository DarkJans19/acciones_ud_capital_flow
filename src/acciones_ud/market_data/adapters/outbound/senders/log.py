"""Outbound notification senders. Email and Telegram log when unconfigured."""

import logging

from acciones_ud.market_data.domain.entities import Notification, Recipient
from acciones_ud.market_data.domain.notifications import IN_APP

logger = logging.getLogger(__name__)


class LogEmailSender:
    channel = "email"

    async def send(self, recipient: Recipient, notification: Notification) -> None:
        logger.info("email notification %s for %s", notification.id, recipient.user_id)


class SimulatedSmsSender:
    channel = "sms"

    async def send(self, recipient: Recipient, notification: Notification) -> None:
        logger.info("sms notification %s for %s", notification.id, recipient.user_id)


class LogTelegramSender:
    channel = "telegram"

    async def send(self, recipient: Recipient, notification: Notification) -> None:
        logger.info("telegram notification %s for %s", notification.id, recipient.user_id)


class InAppSender:
    channel = IN_APP

    async def send(self, recipient: Recipient, notification: Notification) -> None:
        return None


def default_senders() -> list[LogEmailSender | SimulatedSmsSender | LogTelegramSender]:
    return [LogEmailSender(), SimulatedSmsSender(), LogTelegramSender()]
