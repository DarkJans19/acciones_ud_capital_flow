from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from acciones_ud.brokers.adapters.outbound.notifications.brokers_notifier import BrokersNotifier
from acciones_ud.market_data.adapters.outbound.persistence.notification_repository import (
    NotificationRepository,
)
from acciones_ud.market_data.adapters.outbound.persistence.recipient_directory import (
    RecipientDirectory,
)
from acciones_ud.market_data.application.notifier import Notifier
from tests.brokers.fakes import Clock


@pytest.mark.db
async def test_broker_notification_uses_default_preferences_and_persists_delivery(db_session):
    investor = (await db_session.execute(sa.text("SELECT id FROM users LIMIT 1"))).scalar_one()

    @asynccontextmanager
    async def directory():
        yield RecipientDirectory(db_session)

    @asynccontextmanager
    async def notifications():
        yield SimpleNamespace(notifications=NotificationRepository(db_session))

    adapter = BrokersNotifier(directory, Notifier(notifications, [], Clock()))
    for event in ("broker_link_updates", "proposal_updates"):
        await adapter.notify(investor, event, {"status": "sent"})
    rows = (
        await db_session.execute(
            sa.text("""SELECT event_type, channel, status
        FROM notifications n JOIN notification_deliveries d ON d.notification_id=n.id
        WHERE user_id=:id AND event_type IN ('broker_link_updates','proposal_updates')
    """),
            {"id": investor},
        )
    ).all()
    assert sorted(tuple(row) for row in rows) == [
        ("broker_link_updates", "in_app", "sent"),
        ("proposal_updates", "in_app", "sent"),
    ]
