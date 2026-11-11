"""In-memory adapters shared by market_data unit tests."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID, uuid4

from acciones_ud.market_data.domain.catalog_merge import merge_asset, merge_catalog
from acciones_ud.market_data.domain.entities import (
    AlertStatus,
    Comparator,
    Instrument,
    Market,
    Notification,
    PriceAlert,
    Recipient,
    ScheduleOverride,
    Snapshot,
    StoredSnapshot,
    Watchlist,
)
from acciones_ud.market_data.domain.ports import (
    AlertWork,
    AlertWorkFactory,
    CatalogWork,
    CatalogWorkFactory,
    DashboardWork,
    DashboardWorkFactory,
    DirectoryFactory,
    MarketWork,
    MarketWorkFactory,
    NotificationWork,
    NotificationWorkFactory,
    QuoteWork,
    QuoteWorkFactory,
    WatchlistWork,
    WatchlistWorkFactory,
)
from acciones_ud.market_data.domain.search import search_reference
from acciones_ud.shared.domain.errors import AppError, ErrorCode


class MemoryInstruments:
    def __init__(
        self,
        instruments: list[Instrument] | None = None,
        last_reload: datetime | None = None,
    ) -> None:
        self.items: dict[str, Instrument] = {
            instrument.symbol: instrument for instrument in (instruments or [])
        }
        self.last_reload = last_reload
        self.upserts = 0
        self.search_calls = 0

    async def search(
        self,
        query: str,
        exchange: str | None,
        classification: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Instrument], int]:
        self.search_calls += 1
        return search_reference(
            list(self.items.values()), query, exchange, classification, page, page_size
        )

    async def exchanges(self) -> list[Market]:
        codes = sorted({item.exchange for item in self.items.values() if item.listed})
        return [Market(code=code, name=code) for code in codes]

    async def exists(self, symbol: str) -> bool:
        return symbol in self.items

    async def get(self, symbol: str) -> Instrument | None:
        return self.items.get(symbol)

    async def list_symbols(self) -> list[str]:
        return sorted(item.symbol for item in self.items.values() if item.listed)

    async def all_listed(self) -> list[Instrument]:
        return sorted(
            (item for item in self.items.values() if item.listed),
            key=lambda item: item.symbol,
        )

    async def has_instruments(self) -> bool:
        return bool(self.items)

    async def catalog_last_reload(self) -> datetime | None:
        return self.last_reload

    async def set_catalog_last_reload(self, now: datetime) -> None:
        self.last_reload = now

    async def upsert_catalog(self, assets: list[Instrument], now: datetime) -> None:
        self.upserts += 1
        merged = merge_catalog(list(self.items.values()), assets)
        self.items = {item.symbol: item for item in merged}

    async def upsert_one(self, asset: Instrument, now: datetime) -> None:
        self.upserts += 1
        merged = merge_asset(list(self.items.values()), asset)
        self.items = {item.symbol: item for item in merged}


class CatalogWorkStub:
    def __init__(self, instruments: MemoryInstruments) -> None:
        self.instruments = instruments


def catalog_uow(repository: MemoryInstruments) -> CatalogWorkFactory:
    @asynccontextmanager
    async def factory() -> AsyncIterator[CatalogWork]:
        yield CatalogWorkStub(repository)

    return factory


class MemorySnapshots:
    def __init__(self, stored: dict[str, StoredSnapshot] | None = None) -> None:
        self.items = dict(stored or {})
        self.saves = 0

    async def get(self, symbol: str) -> StoredSnapshot | None:
        return self.items.get(symbol)

    async def save(self, symbol: str, snapshot: Snapshot, retrieved_at: datetime) -> None:
        self.saves += 1
        self.items[symbol] = StoredSnapshot(snapshot=snapshot, retrieved_at=retrieved_at)


class QuoteWorkStub:
    def __init__(self, instruments: MemoryInstruments, snapshots: MemorySnapshots) -> None:
        self.instruments = instruments
        self.snapshots = snapshots


def quote_uow(
    instruments: MemoryInstruments, snapshots: MemorySnapshots
) -> QuoteWorkFactory:
    @asynccontextmanager
    async def factory() -> AsyncIterator[QuoteWork]:
        yield QuoteWorkStub(instruments, snapshots)

    return factory


class MemoryMarkets:
    def __init__(self, markets: list[Market] | None = None) -> None:
        self.items = {market.code: market for market in (markets or [])}
        self.override_items: dict[tuple[str, object], ScheduleOverride] = {}

    async def all_markets(self) -> list[Market]:
        return [self.items[code] for code in sorted(self.items)]

    async def market(self, code: str) -> Market | None:
        return self.items.get(code)

    async def set_default_schedule(
        self, code: str, open_at: time, close_at: time
    ) -> Market | None:
        from dataclasses import replace

        market = self.items.get(code)
        if market is None:
            return None
        updated = replace(market, default_open_time=open_at, default_close_time=close_at)
        self.items[code] = updated
        return updated

    async def clear_default_schedule(self, code: str) -> bool:
        from dataclasses import replace

        market = self.items.get(code)
        if market is None or market.default_open_time is None:
            return False
        self.items[code] = replace(market, default_open_time=None, default_close_time=None)
        return True

    async def overrides(
        self, code: str, start: date | None = None, end: date | None = None
    ) -> list[ScheduleOverride]:
        return [
            override
            for (market, _), override in sorted(self.override_items.items())
            if market == code
            and (start is None or override.date >= start)
            and (end is None or override.date <= end)
        ]

    async def override(self, code: str, override_id: object) -> ScheduleOverride | None:
        for (market, _), override in self.override_items.items():
            if market == code and override.id == override_id:
                return override
        return None

    async def add_override(self, override: ScheduleOverride) -> ScheduleOverride:
        key = (override.market_code, override.date)
        if key in self.override_items:
            raise AppError(
                409, ErrorCode.OVERRIDE_EXISTS, "Override already exists."
            )
        self.override_items[key] = override
        return override

    async def update_override(self, override: ScheduleOverride) -> ScheduleOverride | None:
        key = (override.market_code, override.date)
        if key not in self.override_items:
            return None
        self.override_items[key] = override
        return override

    async def delete_override(self, code: str, override_id: object) -> bool:
        for key, override in list(self.override_items.items()):
            if key[0] == code and override.id == override_id:
                del self.override_items[key]
                return True
        return False


class MarketWorkStub:
    def __init__(self, markets: MemoryMarkets) -> None:
        self.markets = markets


def market_uow(repository: MemoryMarkets) -> MarketWorkFactory:
    @asynccontextmanager
    async def factory() -> AsyncIterator[MarketWork]:
        yield MarketWorkStub(repository)

    return factory


class MemoryWatchlists:
    def __init__(self) -> None:
        self.items: dict[UUID, Watchlist] = {}
        self.owners: dict[UUID, object] = {}
        self.owner_locks = 0

    async def list_all(self, user_id: object) -> list[Watchlist]:
        return [
            item
            for watchlist_id, item in self.items.items()
            if self.owners.get(watchlist_id) == user_id
        ]

    async def get(self, user_id: object, watchlist_id: UUID) -> Watchlist | None:
        if self.owners.get(watchlist_id) != user_id:
            return None
        return self.items.get(watchlist_id)

    async def lock_owner(self, user_id: object) -> None:
        self.owner_locks += 1

    async def count(self, user_id: object) -> int:
        return sum(1 for owner in self.owners.values() if owner == user_id)

    async def create(self, user_id: object, name: str, now: datetime) -> Watchlist:
        watchlist = Watchlist(id=uuid4(), name=name, symbols=[])
        self.items[watchlist.id] = watchlist
        self.owners[watchlist.id] = user_id
        return watchlist

    async def add_symbol(
        self, user_id: object, watchlist_id: UUID, symbol: str, now: datetime
    ) -> Watchlist:
        watchlist = self.items[watchlist_id]
        if symbol in watchlist.symbols:
            raise AppError(
                409, ErrorCode.SYMBOL_ALREADY_IN_WATCHLIST, "Already in watchlist."
            )
        updated = Watchlist(
            id=watchlist.id, name=watchlist.name, symbols=[*watchlist.symbols, symbol]
        )
        self.items[watchlist_id] = updated
        return updated

    async def remove_symbol(
        self, user_id: object, watchlist_id: UUID, symbol: str
    ) -> Watchlist | None:
        watchlist = await self.get(user_id, watchlist_id)
        if watchlist is None:
            return None
        updated = Watchlist(
            id=watchlist.id,
            name=watchlist.name,
            symbols=[item for item in watchlist.symbols if item != symbol],
        )
        self.items[watchlist_id] = updated
        return updated

    async def symbols(self, watchlist_id: UUID) -> list[str]:
        return list(self.items[watchlist_id].symbols)


class WatchlistWorkStub:
    def __init__(self, instruments: MemoryInstruments, watchlists: MemoryWatchlists) -> None:
        self.instruments = instruments
        self.watchlists = watchlists


def watchlist_uow(
    instruments: MemoryInstruments, watchlists: MemoryWatchlists
) -> WatchlistWorkFactory:
    @asynccontextmanager
    async def factory() -> AsyncIterator[WatchlistWork]:
        yield WatchlistWorkStub(instruments, watchlists)

    return factory


class MemoryAlerts:
    def __init__(self) -> None:
        self.items: dict[UUID, PriceAlert] = {}

    async def list_all(self, user_id: object) -> list[PriceAlert]:
        return list(self.items.values())

    async def get(self, user_id: object, alert_id: UUID) -> PriceAlert | None:
        return self.items.get(alert_id)

    async def create(
        self, user_id: object, symbol: str, comparator: str, threshold: Decimal, now: datetime
    ) -> PriceAlert:
        alert = PriceAlert(
            id=uuid4(),
            symbol=symbol,
            comparator=Comparator(comparator),
            threshold=threshold,
            status=AlertStatus.ACTIVE,
            created_at=now,
        )
        self.items[alert.id] = alert
        return alert

    async def set_status(
        self, user_id: object, alert_id: UUID, status: str
    ) -> PriceAlert | None:
        alert = self.items.get(alert_id)
        if alert is None:
            return None
        updated = PriceAlert(
            id=alert.id,
            symbol=alert.symbol,
            comparator=alert.comparator,
            threshold=alert.threshold,
            status=AlertStatus(status),
            created_at=alert.created_at,
            triggered_at=alert.triggered_at,
        )
        self.items[alert_id] = updated
        return updated

    async def delete(self, user_id: object, alert_id: UUID) -> bool:
        return self.items.pop(alert_id, None) is not None

    async def active_grouped(self) -> dict[str, list[PriceAlert]]:
        grouped: dict[str, list[PriceAlert]] = {}
        for alert in self.items.values():
            if alert.status is AlertStatus.ACTIVE:
                grouped.setdefault(alert.symbol, []).append(alert)
        return grouped

    async def lock_active(self, alert_id: UUID) -> PriceAlert | None:
        alert = self.items.get(alert_id)
        return alert if alert is not None and alert.status is AlertStatus.ACTIVE else None

    async def record_price(self, alert_id: UUID, price: Decimal) -> None:
        return None

    async def trigger(self, alert_id: UUID, price: Decimal, now: datetime) -> bool:
        alert = self.items.get(alert_id)
        if alert is None or alert.status is not AlertStatus.ACTIVE:
            return False
        self.items[alert_id] = PriceAlert(
            id=alert.id,
            symbol=alert.symbol,
            comparator=alert.comparator,
            threshold=alert.threshold,
            status=AlertStatus.TRIGGERED,
            created_at=alert.created_at,
            triggered_at=now,
        )
        return True


class AlertWorkStub:
    def __init__(self, instruments: MemoryInstruments, alerts: MemoryAlerts) -> None:
        self.instruments = instruments
        self.alerts = alerts


def alert_uow(
    instruments: MemoryInstruments, alerts: MemoryAlerts
) -> AlertWorkFactory:
    @asynccontextmanager
    async def factory() -> AsyncIterator[AlertWork]:
        yield AlertWorkStub(instruments, alerts)

    return factory


class MemoryNotifications:
    def __init__(self) -> None:
        self.items: list[Notification] = []
        self.deliveries: dict[tuple[UUID, str], tuple[str, str | None]] = {}

    async def create(
        self, user_id: object, event_type: str, payload: dict[str, object], now: datetime
    ) -> Notification:
        notification = Notification(
            id=uuid4(), event_type=event_type, payload=payload, created_at=now
        )
        self.items.append(notification)
        return notification

    async def add_delivery(
        self, notification_id: UUID, channel: str, status: str
    ) -> None:
        self.deliveries[(notification_id, channel)] = (status, None)

    async def mark_delivery(
        self, notification_id: UUID, channel: str, status: str, error_code: str | None
    ) -> None:
        self.deliveries[(notification_id, channel)] = (status, error_code)

    async def list_in_app(self, user_id: object, limit: int) -> list[Notification]:
        return list(reversed(self.items))[:limit]


class NotificationWorkStub:
    def __init__(self, notifications: MemoryNotifications) -> None:
        self.notifications = notifications


def notification_uow(notifications: MemoryNotifications) -> NotificationWorkFactory:
    @asynccontextmanager
    async def factory() -> AsyncIterator[NotificationWork]:
        yield NotificationWorkStub(notifications)

    return factory


class RecordingSender:
    def __init__(self, channel: str, error: Exception | None = None) -> None:
        self.channel = channel
        self.error = error
        self.sent: list[tuple[Recipient, Notification]] = []

    async def send(self, recipient: Recipient, notification: Notification) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append((recipient, notification))


class MemoryProfiles:
    def __init__(self, interests: list[str] | None = None, level: str | None = None) -> None:
        self.interests = interests or []
        self.level = level

    async def profile(self, user_id: object) -> tuple[list[str], str | None]:
        return list(self.interests), self.level


class DashboardWorkStub:
    def __init__(self, instruments: MemoryInstruments, profiles: MemoryProfiles) -> None:
        self.instruments = instruments
        self.snapshots = MemorySnapshots()
        self.profile = profiles


def dashboard_uow(
    instruments: MemoryInstruments, profiles: MemoryProfiles
) -> DashboardWorkFactory:
    @asynccontextmanager
    async def factory() -> AsyncIterator[DashboardWork]:
        yield DashboardWorkStub(instruments, profiles)

    return factory


class MemoryDirectory:
    def __init__(self, recipients: list[Recipient] | None = None) -> None:
        self.recipients_value = recipients or []

    async def recipients(self, event_type: str) -> list[Recipient]:
        return list(self.recipients_value)


def directory_uow(directory: MemoryDirectory) -> DirectoryFactory:
    @asynccontextmanager
    async def factory() -> AsyncIterator[MemoryDirectory]:
        yield directory

    return factory
