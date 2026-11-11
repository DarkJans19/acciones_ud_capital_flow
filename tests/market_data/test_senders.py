"""Sender selection and no-destination handling (14.15-14.18)."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from acciones_ud.config.settings import Settings
from acciones_ud.market_data.adapters.outbound.senders.log import (
    LogEmailSender,
    LogTelegramSender,
    SimulatedSmsSender,
)
from acciones_ud.market_data.adapters.outbound.senders.smtp import SmtpEmailSender
from acciones_ud.market_data.adapters.outbound.senders.telegram import TelegramBotSender
from acciones_ud.market_data.application.notifier import Notifier
from acciones_ud.market_data.composition import build_senders
from acciones_ud.market_data.domain.entities import Notification, Recipient
from acciones_ud.market_data.domain.notifications import NoDestinationError
from acciones_ud.market_data.domain.ports import ChannelSender
from tests.support.clock import FakeClock
from tests.support.market_fakes import MemoryNotifications, notification_uow

NOW = datetime(2026, 1, 2, tzinfo=UTC)


def _settings(**overrides: str) -> Settings:
    return Settings(_env_file=None, app_env="test", **overrides)


def _by_channel(senders: list[ChannelSender]) -> dict[str, ChannelSender]:
    return {sender.channel: sender for sender in senders}


def test_log_senders_when_nothing_configured() -> None:
    senders = _by_channel(build_senders(_settings()))
    assert isinstance(senders["email"], LogEmailSender)
    assert isinstance(senders["telegram"], LogTelegramSender)
    assert isinstance(senders["sms"], SimulatedSmsSender)


def test_real_email_sender_when_smtp_host_is_set() -> None:
    senders = _by_channel(
        build_senders(_settings(smtp_host="smtp.example.test", smtp_from="a@example.test"))
    )
    assert isinstance(senders["email"], SmtpEmailSender)
    assert isinstance(senders["telegram"], LogTelegramSender)


def test_real_telegram_sender_when_token_is_set() -> None:
    senders = _by_channel(build_senders(_settings(telegram_bot_token="123:abc")))
    assert isinstance(senders["telegram"], TelegramBotSender)
    assert isinstance(senders["email"], LogEmailSender)


def test_sms_is_always_simulated_even_with_everything_set() -> None:
    senders = _by_channel(
        build_senders(
            _settings(
                smtp_host="smtp.example.test",
                smtp_from="a@example.test",
                telegram_bot_token="123:abc",
            )
        )
    )
    assert isinstance(senders["sms"], SimulatedSmsSender)


async def test_smtp_sender_without_email_raises_no_destination() -> None:
    sender = SmtpEmailSender("smtp.example.test", 587, None, None, "a@example.test")
    notification = Notification(uuid4(), "price_changes", {}, NOW)
    recipient = Recipient(uuid4(), frozenset({"email"}), email=None)
    with pytest.raises(NoDestinationError):
        await sender.send(recipient, notification)


async def test_telegram_sender_without_chat_id_raises_no_destination() -> None:
    sender = TelegramBotSender("123:abc")
    notification = Notification(uuid4(), "price_changes", {}, NOW)
    recipient = Recipient(uuid4(), frozenset({"telegram"}), telegram_chat_id=None)
    with pytest.raises(NoDestinationError):
        await sender.send(recipient, notification)


async def test_dispatch_records_no_destination_and_keeps_in_app() -> None:
    notifications = MemoryNotifications()
    senders = [
        SmtpEmailSender("smtp.example.test", 587, None, None, "a@example.test"),
        TelegramBotSender("123:abc"),
    ]
    notifier = Notifier(notification_uow(notifications), senders, FakeClock(NOW))

    # No email address and no telegram chat id for the enabled external channels.
    recipient = Recipient(
        uuid4(), frozenset({"in_app", "email", "telegram"}), email=None, telegram_chat_id=None
    )
    await notifier.notify([recipient], "price_changes", {"symbol": "AAPL"})

    notification = notifications.items[0]
    stored = {
        channel: value
        for (notification_id, channel), value in notifications.deliveries.items()
        if notification_id == notification.id
    }
    assert stored["in_app"] == ("sent", None)
    assert stored["email"] == ("failed", "no_destination")
    assert stored["telegram"] == ("failed", "no_destination")
