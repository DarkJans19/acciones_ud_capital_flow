# Feature: identity-market-backend, Property 25: Notification delivery isolation

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from hypothesis import given
from hypothesis import strategies as st

from acciones_ud.market_data.application.notifier import Notifier
from acciones_ud.market_data.domain.entities import Recipient
from tests.support.clock import FakeClock
from tests.support.market_fakes import (
    MemoryNotifications,
    RecordingSender,
    notification_uow,
)

NOW = datetime(2026, 1, 2, tzinfo=UTC)
EXTERNAL = ("email", "sms", "telegram")


@given(
    channels=st.sets(st.sampled_from(EXTERNAL), max_size=3),
    failing=st.sets(st.sampled_from(EXTERNAL), max_size=3),
)
def test_delivery_isolation(channels: set[str], failing: set[str]) -> None:
    notifications = MemoryNotifications()
    senders = [
        RecordingSender(channel, RuntimeError("boom") if channel in failing else None)
        for channel in EXTERNAL
    ]
    notifier = Notifier(notification_uow(notifications), senders, FakeClock(NOW))
    recipient = Recipient(
        user_id=uuid4(), channels=frozenset({"in_app", *channels})
    )

    asyncio.run(
        notifier.notify([recipient], "price_changes", {"symbol": "AAPL"})
    )

    assert len(notifications.items) == 1
    notification = notifications.items[0]
    stored = {
        channel: status
        for (notification_id, channel), (status, _) in notifications.deliveries.items()
        if notification_id == notification.id
    }
    assert set(stored) == {"in_app", *channels}
    assert stored["in_app"] == "sent"
    for channel in channels:
        assert stored[channel] == ("failed" if channel in failing else "sent")
        sender = next(item for item in senders if item.channel == channel)
        assert len(sender.sent) == (0 if channel in failing else 1)
