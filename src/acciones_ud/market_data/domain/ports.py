"""Ports of the market data module. Adapters implement these protocols."""

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from datetime import date, datetime, time
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from acciones_ud.market_data.domain.entities import (
    BarsPage,
    CalendarSession,
    Instrument,
    LatestQuoteDoc,
    Market,
    MarketClock,
    Notification,
    PriceAlert,
    PriceUpdate,
    Recipient,
    ScheduleOverride,
    Snapshot,
    StoredSnapshot,
    Watchlist,
)


class AlpacaBrokerMarketPort(Protocol):
    async def list_assets(self) -> list[Instrument]: ...

    async def get_asset(self, symbol: str) -> Instrument: ...

    async def calendar(self, start: date, end: date) -> list[CalendarSession]: ...

    async def clock(self) -> MarketClock: ...


class AlpacaDataPort(Protocol):
    async def snapshot(self, symbol: str) -> Snapshot: ...

    async def snapshots(self, symbols: list[str]) -> dict[str, Snapshot]: ...

    async def bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        page_size: int,
        page_token: str | None,
    ) -> BarsPage: ...

    async def latest_quote(self, symbol: str) -> LatestQuoteDoc: ...


class StreamUpstreamPort(Protocol):
    def stream(self) -> AsyncIterator[PriceUpdate]: ...

    async def subscribe(self, symbols: set[str]) -> None: ...

    async def close(self) -> None: ...


class InstrumentRepository(Protocol):
    async def search(
        self,
        query: str,
        exchange: str | None,
        classification: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Instrument], int]: ...

    async def exchanges(self) -> list[Market]: ...

    async def exists(self, symbol: str) -> bool: ...

    async def get(self, symbol: str) -> Instrument | None: ...

    async def list_symbols(self) -> list[str]: ...

    async def all_listed(self) -> list[Instrument]: ...

    async def has_instruments(self) -> bool: ...

    async def upsert_catalog(self, assets: list[Instrument], now: datetime) -> None: ...

    async def upsert_one(self, asset: Instrument, now: datetime) -> None: ...

    async def catalog_last_reload(self) -> datetime | None: ...

    async def set_catalog_last_reload(self, now: datetime) -> None: ...


class SnapshotRepository(Protocol):
    async def get(self, symbol: str) -> StoredSnapshot | None: ...

    async def save(self, symbol: str, snapshot: Snapshot, retrieved_at: datetime) -> None: ...


class MarketRepository(Protocol):
    async def all_markets(self) -> list[Market]: ...

    async def market(self, code: str) -> Market | None: ...

    async def set_default_schedule(
        self, code: str, open_at: time, close_at: time
    ) -> Market | None: ...

    async def clear_default_schedule(self, code: str) -> bool: ...

    async def overrides(
        self, code: str, start: date | None, end: date | None
    ) -> list[ScheduleOverride]: ...

    async def override(self, code: str, override_id: UUID) -> ScheduleOverride | None: ...

    async def add_override(self, override: ScheduleOverride) -> ScheduleOverride: ...

    async def update_override(self, override: ScheduleOverride) -> ScheduleOverride | None: ...

    async def delete_override(self, code: str, override_id: UUID) -> bool: ...


class WatchlistRepository(Protocol):
    async def list_all(self, user_id: UUID) -> list[Watchlist]: ...

    async def get(self, user_id: UUID, watchlist_id: UUID) -> Watchlist | None: ...

    async def lock_owner(self, user_id: UUID) -> None: ...

    async def count(self, user_id: UUID) -> int: ...

    async def create(self, user_id: UUID, name: str, now: datetime) -> Watchlist: ...

    async def add_symbol(
        self, user_id: UUID, watchlist_id: UUID, symbol: str, now: datetime
    ) -> Watchlist: ...

    async def remove_symbol(
        self, user_id: UUID, watchlist_id: UUID, symbol: str
    ) -> Watchlist | None: ...

    async def symbols(self, watchlist_id: UUID) -> list[str]: ...


class AlertRepository(Protocol):
    async def list_all(self, user_id: UUID) -> list[PriceAlert]: ...

    async def get(self, user_id: UUID, alert_id: UUID) -> PriceAlert | None: ...

    async def create(
        self, user_id: UUID, symbol: str, comparator: str, threshold: Decimal, now: datetime
    ) -> PriceAlert: ...

    async def set_status(
        self, user_id: UUID, alert_id: UUID, status: str
    ) -> PriceAlert | None: ...

    async def delete(self, user_id: UUID, alert_id: UUID) -> bool: ...

    async def active_grouped(self) -> dict[str, list[PriceAlert]]: ...

    async def lock_active(self, alert_id: UUID) -> PriceAlert | None: ...

    async def record_price(self, alert_id: UUID, price: Decimal) -> None: ...

    async def trigger(self, alert_id: UUID, price: Decimal, now: datetime) -> bool: ...


class NotificationRepository(Protocol):
    async def create(
        self, user_id: UUID, event_type: str, payload: dict[str, object], now: datetime
    ) -> Notification: ...

    async def add_delivery(self, notification_id: UUID, channel: str, status: str) -> None: ...

    async def mark_delivery(
        self, notification_id: UUID, channel: str, status: str, error_code: str | None
    ) -> None: ...

    async def list_in_app(self, user_id: UUID, limit: int) -> list[Notification]: ...


class RecipientDirectory(Protocol):
    async def recipients(self, event_type: str) -> list[Recipient]: ...


class UserProfileReader(Protocol):
    async def profile(self, user_id: UUID) -> tuple[list[str], str | None]: ...


class ChannelSender(Protocol):
    channel: str

    async def send(self, recipient: Recipient, notification: Notification) -> None: ...


class DirectoryFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[RecipientDirectory]: ...


class CatalogWork(Protocol):
    @property
    def instruments(self) -> InstrumentRepository: ...


class CatalogWorkFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[CatalogWork]: ...


class QuoteWork(Protocol):
    @property
    def instruments(self) -> InstrumentRepository: ...

    @property
    def snapshots(self) -> SnapshotRepository: ...


class QuoteWorkFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[QuoteWork]: ...


class MarketWork(Protocol):
    @property
    def markets(self) -> MarketRepository: ...


class MarketWorkFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[MarketWork]: ...


class WatchlistWork(Protocol):
    @property
    def instruments(self) -> InstrumentRepository: ...

    @property
    def watchlists(self) -> WatchlistRepository: ...


class WatchlistWorkFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[WatchlistWork]: ...


class AlertWork(Protocol):
    @property
    def instruments(self) -> InstrumentRepository: ...

    @property
    def alerts(self) -> AlertRepository: ...


class AlertWorkFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[AlertWork]: ...


class NotificationWork(Protocol):
    @property
    def notifications(self) -> NotificationRepository: ...


class NotificationWorkFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[NotificationWork]: ...


class DashboardWork(Protocol):
    @property
    def instruments(self) -> InstrumentRepository: ...

    @property
    def snapshots(self) -> SnapshotRepository: ...

    @property
    def profile(self) -> UserProfileReader: ...


class DashboardWorkFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[DashboardWork]: ...
