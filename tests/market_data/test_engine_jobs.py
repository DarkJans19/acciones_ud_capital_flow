from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from acciones_ud.market_data.adapters.inbound.jobs.clock_watcher import ClockWatcher
from acciones_ud.market_data.adapters.inbound.jobs.price_alert_loop import PriceAlertLoop
from acciones_ud.market_data.adapters.outbound.alpaca.fake_broker import FakeAlpacaBrokerMarket
from acciones_ud.market_data.adapters.outbound.alpaca.fake_data import FakeAlpacaData
from acciones_ud.market_data.application.notifier import Notifier
from acciones_ud.market_data.domain.entities import (
    AlertStatus,
    Comparator,
    PriceAlert,
    Recipient,
    Snapshot,
)
from tests.support.clock import FakeClock
from tests.support.market_fakes import (
    MemoryAlerts,
    MemoryDirectory,
    MemoryInstruments,
    MemoryNotifications,
    RecordingSender,
    alert_uow,
    directory_uow,
    notification_uow,
)

NOW = datetime(2026, 1, 2, 14, tzinfo=UTC)


def notifier(notifications: MemoryNotifications) -> Notifier:
    return Notifier(
        notification_uow(notifications),
        [RecordingSender("email")],
        FakeClock(NOW),
    )


async def test_clock_watcher_emits_only_transitions() -> None:
    broker = FakeAlpacaBrokerMarket()
    directory = MemoryDirectory([Recipient(uuid4(), frozenset({"in_app"}))])
    notifications = MemoryNotifications()
    watcher = ClockWatcher(broker, directory_uow(directory), notifier(notifications), 60)

    broker.clock_value = replace(broker.clock_value, is_open=True)
    await watcher.run_once()
    assert notifications.items == []

    broker.clock_value = replace(broker.clock_value, is_open=False)
    await watcher.run_once()
    assert [item.event_type for item in notifications.items] == ["market_close"]


async def test_alert_engine_triggers_and_notifies_once() -> None:
    alerts = MemoryAlerts()
    owner = uuid4()
    alert = PriceAlert(
        id=uuid4(),
        symbol="AAPL",
        comparator=Comparator.ABOVE,
        threshold=Decimal("100"),
        status=AlertStatus.ACTIVE,
        created_at=NOW,
        user_id=owner,
        last_evaluated_price=Decimal("90"),
    )
    alerts.items[alert.id] = alert

    data = FakeAlpacaData()
    data.snapshots_value = {"AAPL": Snapshot(last_trade_price=Decimal("110"))}
    directory = MemoryDirectory([Recipient(owner, frozenset({"in_app"}))])
    notifications = MemoryNotifications()
    loop = PriceAlertLoop(
        alert_uow(MemoryInstruments(), alerts),
        data,
        directory_uow(directory),
        notifier(notifications),
        FakeClock(NOW),
        60,
    )

    await loop.run_once()
    assert alerts.items[alert.id].status is AlertStatus.TRIGGERED
    assert [item.event_type for item in notifications.items] == ["price_changes"]

    await loop.run_once()
    assert len(notifications.items) == 1


async def test_alert_engine_skips_unavailable_prices() -> None:
    alerts = MemoryAlerts()
    alert = PriceAlert(
        id=uuid4(),
        symbol="AAPL",
        comparator=Comparator.ABOVE,
        threshold=Decimal("100"),
        status=AlertStatus.ACTIVE,
        user_id=uuid4(),
        last_evaluated_price=Decimal("90"),
    )
    alerts.items[alert.id] = alert
    data = FakeAlpacaData()
    data.snapshots_value = {"AAPL": Snapshot(last_trade_price=None)}
    notifications = MemoryNotifications()
    loop = PriceAlertLoop(
        alert_uow(MemoryInstruments(), alerts),
        data,
        directory_uow(MemoryDirectory()),
        notifier(notifications),
        FakeClock(NOW),
        60,
    )

    await loop.run_once()
    assert alerts.items[alert.id].status is AlertStatus.ACTIVE
    assert notifications.items == []
