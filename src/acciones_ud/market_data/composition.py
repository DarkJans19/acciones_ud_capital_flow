"""Composición de puertos y adaptadores de datos bursátiles."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import FastAPI, Request

from acciones_ud.market_data.adapters.inbound.jobs.clock_watcher import ClockWatcher
from acciones_ud.market_data.adapters.inbound.jobs.price_alert_loop import PriceAlertLoop
from acciones_ud.market_data.adapters.outbound.alpaca.broker_client import (
    AlpacaBrokerMarketClient,
)
from acciones_ud.market_data.adapters.outbound.alpaca.data_client import AlpacaDataClient
from acciones_ud.market_data.adapters.outbound.alpaca.stream_client import AlpacaStreamClient
from acciones_ud.market_data.adapters.outbound.persistence.alert_repository import (
    AlertRepository,
)
from acciones_ud.market_data.adapters.outbound.persistence.instrument_repository import (
    InstrumentRepository,
)
from acciones_ud.market_data.adapters.outbound.persistence.market_repository import (
    MarketRepository,
)
from acciones_ud.market_data.adapters.outbound.persistence.notification_repository import (
    NotificationRepository,
)
from acciones_ud.market_data.adapters.outbound.persistence.recipient_directory import (
    RecipientDirectory,
)
from acciones_ud.market_data.adapters.outbound.persistence.snapshot_repository import (
    SnapshotRepository,
)
from acciones_ud.market_data.adapters.outbound.persistence.user_profile_reader import (
    UserProfileReader,
)
from acciones_ud.market_data.adapters.outbound.persistence.watchlist_repository import (
    WatchlistRepository,
)
from acciones_ud.market_data.adapters.outbound.senders.log import default_senders
from acciones_ud.market_data.application.alerts import AlertService
from acciones_ud.market_data.application.asset_detail import AssetDetailService
from acciones_ud.market_data.application.calendar import (
    CalendarService,
    ClockService,
    MarketStatusService,
)
from acciones_ud.market_data.application.candles import CandleService
from acciones_ud.market_data.application.catalog import CatalogService
from acciones_ud.market_data.application.dashboard import DashboardService
from acciones_ud.market_data.application.depth import DepthService
from acciones_ud.market_data.application.exchanges import ExchangesService
from acciones_ud.market_data.application.notifier import Notifier
from acciones_ud.market_data.application.quotes import QuoteService
from acciones_ud.market_data.application.schedule_admin import ScheduleAdminService
from acciones_ud.market_data.application.search import SearchService
from acciones_ud.market_data.application.stream_hub import StreamHub
from acciones_ud.market_data.application.watchlists import WatchlistService
from acciones_ud.market_data.domain.ports import (
    AlertWork,
    AlpacaBrokerMarketPort,
    AlpacaDataPort,
    CatalogWork,
    DashboardWork,
    MarketWork,
    NotificationWork,
    QuoteWork,
    WatchlistWork,
)
from acciones_ud.market_data.domain.streaming import SubscriptionRegistry
from acciones_ud.shared.domain.clock import Clock, SystemClock


def register(app: FastAPI) -> None:
    from acciones_ud.market_data.adapters.inbound.http.routers import (
        admin_markets,
        alerts,
        dashboard,
        instruments,
        markets,
        notifications,
        stream,
        watchlists,
    )

    app.include_router(markets.router, prefix="/api/v1")
    app.include_router(instruments.router, prefix="/api/v1")
    app.include_router(admin_markets.router, prefix="/api/v1")
    app.include_router(watchlists.router, prefix="/api/v1")
    app.include_router(alerts.router, prefix="/api/v1")
    app.include_router(notifications.router, prefix="/api/v1")
    app.include_router(dashboard.router, prefix="/api/v1")
    app.include_router(stream.router)


def _override(request: Request, name: str) -> Any:
    return getattr(request.app.state, name, None)


def clock(request: Request) -> Clock:
    override = _override(request, "clock")
    if override is not None:
        return cast(Clock, override)
    return SystemClock()


def broker_market(request: Request) -> AlpacaBrokerMarketPort:
    override = _override(request, "alpaca_broker_market")
    if override is not None:
        return cast(AlpacaBrokerMarketPort, override)
    return AlpacaBrokerMarketClient(request.app.state.alpaca_broker)


@asynccontextmanager
async def catalog_uow() -> AsyncIterator[CatalogWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:

        class Work:
            instruments = InstrumentRepository(session)

        yield Work()


@asynccontextmanager
async def quote_uow() -> AsyncIterator[QuoteWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:

        class Work:
            instruments = InstrumentRepository(session)
            snapshots = SnapshotRepository(session)

        yield Work()


@asynccontextmanager
async def market_uow() -> AsyncIterator[MarketWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:

        class Work:
            markets = MarketRepository(session)

        yield Work()


@asynccontextmanager
async def watchlist_uow() -> AsyncIterator[WatchlistWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:

        class Work:
            instruments = InstrumentRepository(session)
            watchlists = WatchlistRepository(session)

        yield Work()


@asynccontextmanager
async def alert_uow() -> AsyncIterator[AlertWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:

        class Work:
            instruments = InstrumentRepository(session)
            alerts = AlertRepository(session)

        yield Work()


@asynccontextmanager
async def notification_uow() -> AsyncIterator[NotificationWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:

        class Work:
            notifications = NotificationRepository(session)

        yield Work()


@asynccontextmanager
async def dashboard_uow() -> AsyncIterator[DashboardWork]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:

        class Work:
            instruments = InstrumentRepository(session)
            snapshots = SnapshotRepository(session)
            profile = UserProfileReader(session)

        yield Work()


@asynccontextmanager
async def directory_uow() -> AsyncIterator[RecipientDirectory]:
    from acciones_ud.shared.infrastructure.db import unit_of_work

    async with unit_of_work() as session:
        yield RecipientDirectory(session)


def data_client(request: Request) -> AlpacaDataPort:
    override = _override(request, "alpaca_data_port")
    if override is not None:
        return cast(AlpacaDataPort, override)
    settings = request.app.state.settings
    return AlpacaDataClient(request.app.state.alpaca_data, settings.alpaca_data_feed)


def catalog_service(request: Request) -> CatalogService:
    override = _override(request, "catalog_service")
    if isinstance(override, CatalogService):
        return override
    settings = request.app.state.settings
    return CatalogService(
        catalog_uow,
        broker_market(request),
        clock(request),
        int(settings.catalog_max_age_hours),
    )


def search_service(request: Request) -> SearchService:
    override = _override(request, "search_service")
    if isinstance(override, SearchService):
        return override
    return SearchService(catalog_uow, catalog_service(request))


def exchanges_service(request: Request) -> ExchangesService:
    override = _override(request, "exchanges_service")
    if isinstance(override, ExchangesService):
        return override
    return ExchangesService(catalog_uow, catalog_service(request))


def asset_detail_service(request: Request) -> AssetDetailService:
    override = _override(request, "asset_detail_service")
    if isinstance(override, AssetDetailService):
        return override
    return AssetDetailService(catalog_uow, broker_market(request), clock(request))


def quote_service(request: Request) -> QuoteService:
    override = _override(request, "quote_service")
    if isinstance(override, QuoteService):
        return override
    settings = request.app.state.settings
    return QuoteService(
        quote_uow,
        data_client(request),
        clock(request),
        int(settings.price_staleness_threshold_seconds),
    )


def candle_service(request: Request) -> CandleService:
    override = _override(request, "candle_service")
    if isinstance(override, CandleService):
        return override
    settings = request.app.state.settings
    return CandleService(quote_uow, data_client(request), settings.alpaca_data_feed)


def depth_service(request: Request) -> DepthService:
    override = _override(request, "depth_service")
    if isinstance(override, DepthService):
        return override
    settings = request.app.state.settings
    return DepthService(
        quote_uow,
        data_client(request),
        clock(request),
        settings.alpaca_data_feed,
        int(settings.price_staleness_threshold_seconds),
    )


def calendar_service(request: Request) -> CalendarService:
    override = _override(request, "calendar_service")
    if isinstance(override, CalendarService):
        return override
    return CalendarService(market_uow, broker_market(request))


def market_status_service(request: Request) -> MarketStatusService:
    override = _override(request, "market_status_service")
    if isinstance(override, MarketStatusService):
        return override
    return MarketStatusService(market_uow, broker_market(request))


def clock_service(request: Request) -> ClockService:
    override = _override(request, "clock_service")
    if isinstance(override, ClockService):
        return override
    return ClockService(broker_market(request))


def schedule_admin_service(request: Request) -> ScheduleAdminService:
    override = _override(request, "schedule_admin_service")
    if isinstance(override, ScheduleAdminService):
        return override
    return ScheduleAdminService(market_uow)


def watchlist_service(request: Request) -> WatchlistService:
    override = _override(request, "watchlist_service")
    if isinstance(override, WatchlistService):
        return override
    return WatchlistService(watchlist_uow, clock(request))


def alert_service(request: Request) -> AlertService:
    override = _override(request, "alert_service")
    if isinstance(override, AlertService):
        return override
    return AlertService(alert_uow, clock(request))


def notifier(request: Request) -> Notifier:
    override = _override(request, "notifier")
    if isinstance(override, Notifier):
        return override
    return Notifier(notification_uow, list(default_senders()), clock(request))


def dashboard_service(request: Request) -> DashboardService:
    override = _override(request, "dashboard_service")
    if isinstance(override, DashboardService):
        return override
    settings = request.app.state.settings
    defaults = [
        item.strip()
        for item in settings.dashboard_default_symbols.split(",")
        if item.strip()
    ]
    return DashboardService(
        dashboard_uow, data_client(request), broker_market(request), defaults
    )


async def startup(app: FastAPI) -> None:
    settings = app.state.settings
    app.state.market_data_jobs = []

    if settings.price_streaming_enabled.lower() == "true":
        key = (
            settings.alpaca_broker_api_key.get_secret_value()
            if settings.alpaca_broker_api_key
            else ""
        )
        secret = (
            settings.alpaca_broker_api_secret.get_secret_value()
            if settings.alpaca_broker_api_secret
            else ""
        )
        upstream = AlpacaStreamClient(
            f"{(settings.alpaca_stream_base_url or '').rstrip('/')}"
            f"/v2/{settings.alpaca_data_feed}",
            key,
            secret,
        )

        async def catalog_symbols() -> set[str]:
            async with catalog_uow() as work:
                return set(await work.instruments.list_symbols())

        hub = StreamHub(SubscriptionRegistry(), upstream, catalog_symbols)
        app.state.stream_hub = hub
        hub.start()

    if settings.alert_engine_enabled.lower() == "true":
        notifier_instance = Notifier(
            notification_uow, list(default_senders()), SystemClock()
        )
        alert_loop = PriceAlertLoop(
            alert_uow,
            AlpacaDataClient(app.state.alpaca_data, settings.alpaca_data_feed),
            directory_uow,
            notifier_instance,
            SystemClock(),
            int(settings.alert_evaluation_interval_seconds),
        )
        watcher = ClockWatcher(
            AlpacaBrokerMarketClient(app.state.alpaca_broker),
            directory_uow,
            notifier_instance,
            int(settings.market_clock_check_interval_seconds),
        )
        alert_loop.start()
        watcher.start()
        app.state.market_data_jobs = [alert_loop, watcher]


async def shutdown(app: FastAPI) -> None:
    hub = getattr(app.state, "stream_hub", None)
    if hub is not None:
        await hub.stop()
    for job in getattr(app.state, "market_data_jobs", []):
        await job.stop()
