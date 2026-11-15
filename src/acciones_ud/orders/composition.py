"""MOD-03 composition. Application services depend exclusively on their ports."""

from decimal import Decimal, InvalidOperation
from typing import cast
from uuid import UUID

from fastapi import FastAPI, Request

from acciones_ud.config.settings import Settings
from acciones_ud.identity import composition as identity
from acciones_ud.identity.adapters.outbound.security.cipher import SecretCipher
from acciones_ud.identity.adapters.outbound.security.totp import TotpProvider
from acciones_ud.identity.application.account import AccountService
from acciones_ud.identity.application.order_authorization import OrderTotpService
from acciones_ud.market_data import composition as market_data
from acciones_ud.orders.adapters.inbound.http.routers import broker_reviews, orders
from acciones_ud.orders.adapters.inbound.jobs.order_reconcile_job import OrderReconcileJob
from acciones_ud.orders.adapters.inbound.jobs.order_scheduler_job import OrderSchedulerJob
from acciones_ud.orders.adapters.outbound.alpaca.orders_client import AlpacaOrdersClient
from acciones_ud.orders.adapters.outbound.alpaca.positions_client import AlpacaPositionsClient
from acciones_ud.orders.adapters.outbound.brokers.null_broker_link import NullBrokerLink
from acciones_ud.orders.adapters.outbound.identity.account_reader import IdentityAccountReader
from acciones_ud.orders.adapters.outbound.identity.controls_reader import IdentityControlsReader
from acciones_ud.orders.adapters.outbound.identity.totp_verifier import IdentityTotpVerifier
from acciones_ud.orders.adapters.outbound.market_data.asset_reader import MarketAssetReader
from acciones_ud.orders.adapters.outbound.market_data.market_session import MarketSessionAdapter
from acciones_ud.orders.adapters.outbound.market_data.quote_reader import MarketQuoteReader
from acciones_ud.orders.adapters.outbound.notifications.order_notifier import OrderNotifierAdapter
from acciones_ud.orders.adapters.outbound.persistence.unit_of_work import order_uow
from acciones_ud.orders.adapters.outbound.wallet.buying_power import WalletBuyingPowerAdapter
from acciones_ud.orders.application.context import OrderContext
from acciones_ud.orders.application.order_reconciler import OrderReconciler
from acciones_ud.orders.application.order_scheduler import OrderScheduler
from acciones_ud.orders.application.order_service import OrderService
from acciones_ud.orders.application.schedule_change import ScheduleChangeService
from acciones_ud.orders.domain.model import OrderConfig
from acciones_ud.orders.domain.ports import BrokerLinkPort
from acciones_ud.shared.domain.clock import SystemClock


class InstalledBrokerLink:
    """MOD-06 may install its port after register and before startup."""

    def __init__(self, app: FastAPI) -> None:
        self.app, self.default = app, NullBrokerLink()

    @property
    def port(self) -> BrokerLinkPort:
        return cast(BrokerLinkPort, getattr(self.app.state, "order_broker_link", self.default))

    async def reviewing_broker(self, investor_id: UUID) -> UUID | None:
        return await self.port.reviewing_broker(investor_id)

    async def is_linked(self, broker_id: UUID, investor_id: UUID) -> bool:
        return await self.port.is_linked(broker_id, investor_id)

    async def linked_investors(self, broker_id: UUID) -> list[UUID]:
        return await self.port.linked_investors(broker_id)


def order_config(settings: Settings) -> OrderConfig:
    # Settings are range-checked at startup. Invalid syntax also reports names only
    # when constructing an app for OpenAPI without entering its lifespan.
    values: dict[str, Decimal] = {}
    for name in (
        "order_reference_commission_rate",
        "order_reauth_price_deviation_pct",
        "order_alpaca_submit_timeout_seconds",
    ):
        try:
            values[name] = Decimal(getattr(settings, name))
            if not values[name].is_finite():
                raise ValueError()
        except (InvalidOperation, ValueError):
            raise RuntimeError("Missing or invalid configuration: " + name.upper()) from None
    integers: dict[str, int] = {}
    for name in ("order_reauth_window_minutes", "order_local_max_age_days"):
        try:
            integers[name] = int(getattr(settings, name))
        except ValueError:
            raise RuntimeError("Missing or invalid configuration: " + name.upper()) from None
    return OrderConfig(
        values["order_reference_commission_rate"],
        values["order_reauth_price_deviation_pct"],
        integers["order_reauth_window_minutes"],
        integers["order_local_max_age_days"],
        float(values["order_alpaca_submit_timeout_seconds"]),
    )


def register(app: FastAPI) -> None:
    settings, clock = app.state.settings, SystemClock()
    scope = Request({"type": "http", "app": app})

    def totp_service() -> OrderTotpService:
        return OrderTotpService(
            identity.auth_uow,
            SecretCipher(settings.totp_encryption_key.get_secret_value()),
            TotpProvider(),
        )

    context = OrderContext(
        uow=order_uow,
        accounts=IdentityAccountReader(identity.kyc_uow),
        controls=IdentityControlsReader(AccountService(identity.account_uow)),
        totp=IdentityTotpVerifier(totp_service),
        quotes=MarketQuoteReader(lambda: market_data.quote_service(scope)),
        assets=MarketAssetReader(
            market_data.catalog_uow, lambda: market_data.catalog_service(scope)
        ),
        sessions=MarketSessionAdapter(lambda: market_data.calendar_service(scope)),
        buying_power=WalletBuyingPowerAdapter(app.state.wallet_funding_port),
        positions=AlpacaPositionsClient(lambda: app.state.alpaca_broker),
        alpaca=AlpacaOrdersClient(lambda: app.state.alpaca_broker),
        brokers=InstalledBrokerLink(app),
        notifier=OrderNotifierAdapter(market_data.directory_uow, market_data.notifier(scope)),
        clock=clock,
        config=order_config(settings),
    )
    service = OrderService(context)
    app.state.order_context = context
    app.state.order_service = service
    app.state.order_review_service = service.reviews
    app.state.order_schedule_change_port = ScheduleChangeService(context)
    app.state.order_reconciler = OrderReconciler(context)
    app.state.order_scheduler = OrderScheduler(context, service)
    for router in (orders.router, broker_reviews.router):
        app.include_router(router, prefix="/api/v1")


async def startup(app: FastAPI) -> None:
    app.state.order_jobs = []
    settings = app.state.settings
    if settings.orders_jobs_enabled.lower() != "true":
        return
    jobs = [
        OrderReconcileJob(
            app.state.order_reconciler,
            int(settings.order_reconcile_interval_seconds),
            "order-reconcile",
        ),
        OrderSchedulerJob(
            app.state.order_scheduler,
            int(settings.order_scheduler_interval_seconds),
            "order-scheduler",
        ),
    ]
    app.state.order_jobs = jobs
    for job in jobs:
        job.start()


async def shutdown(app: FastAPI) -> None:
    for job in getattr(app.state, "order_jobs", []):
        await job.stop()
