"""MOD-06 wiring; all I/O stays lazy until an authorized request or job."""

from decimal import Decimal
from typing import cast
from uuid import UUID

from fastapi import FastAPI, Request

from acciones_ud.brokers.adapters.inbound.http import (
    broker_clients_router,
    broker_links_router,
    broker_proposals_router,
    directory_router,
    links_router,
    proposals_router,
)
from acciones_ud.brokers.adapters.inbound.jobs.expiry_job import ExpiryJob
from acciones_ud.brokers.adapters.outbound.broker_link_adapter import BrokerLinkAdapter
from acciones_ud.brokers.adapters.outbound.identity.associated_broker_reader import (
    AssociatedBrokerReader,
)
from acciones_ud.brokers.adapters.outbound.identity.broker_directory import BrokerDirectory
from acciones_ud.brokers.adapters.outbound.identity.broker_request_reader import BrokerRequestReader
from acciones_ud.brokers.adapters.outbound.identity.controls_reader import ControlsReader
from acciones_ud.brokers.adapters.outbound.identity.linked_account_reader import LinkedAccountReader
from acciones_ud.brokers.adapters.outbound.identity.totp_verifier import TotpVerifier
from acciones_ud.brokers.adapters.outbound.market_data.quote_reader import QuoteReader
from acciones_ud.brokers.adapters.outbound.notifications.brokers_notifier import BrokersNotifier
from acciones_ud.brokers.adapters.outbound.orders.order_creation import OrderCreation
from acciones_ud.brokers.adapters.outbound.orders.order_query import OrderQuery
from acciones_ud.brokers.adapters.outbound.persistence.unit_of_work import broker_uow
from acciones_ud.brokers.application.context import BrokerContext
from acciones_ud.brokers.application.expiry_service import ExpiryService
from acciones_ud.brokers.domain import ports as p
from acciones_ud.brokers.domain.entities import BrokersConfig
from acciones_ud.config.settings import Settings
from acciones_ud.identity import composition as identity
from acciones_ud.identity.adapters.outbound.security.cipher import SecretCipher
from acciones_ud.identity.adapters.outbound.security.totp import TotpProvider
from acciones_ud.identity.application.account import AccountService
from acciones_ud.identity.application.order_authorization import OrderTotpService
from acciones_ud.market_data import composition as market_data
from acciones_ud.orders.domain.model import Raw
from acciones_ud.shared.domain.clock import SystemClock


class InstalledOrderPorts:
    def __init__(self, app: FastAPI) -> None:
        self.app = app

    async def create(self, command: p.ProposalOrderCommand) -> p.OrderCreated | p.OrderRejected:
        port = cast(p.OrderCreationPort, self.app.state.order_proposal_creation)
        return await port.create(command)

    async def list_for_investor(self, investor_id: UUID, filters: p.OrderFilters) -> Raw:
        port = cast(p.OrderQueryPort, self.app.state.order_query_port)
        return await port.list_for_investor(investor_id, filters)

    async def find_by_idempotency_key(
        self, investor_id: UUID, key: str, expected: p.ProposalOrderCommand | None = None
    ) -> UUID | None:
        port = cast(p.OrderQueryPort, self.app.state.order_query_port)
        return await port.find_by_idempotency_key(investor_id, key, expected)


def config(settings: Settings) -> BrokersConfig:
    parsed = {}
    for name, low, high in (
        ("broker_link_request_ttl_days", 1, 90),
        ("proposal_ttl_hours", 1, 720),
        ("brokers_expiry_interval_seconds", 10, 86400),
    ):
        try:
            value = int(getattr(settings, name))
            if not low <= value <= high:
                raise ValueError()
            parsed[name] = value
        except (ValueError, TypeError):
            raise RuntimeError("Missing or invalid configuration: " + name.upper()) from None
    return BrokersConfig(
        parsed["broker_link_request_ttl_days"],
        parsed["proposal_ttl_hours"],
        settings.broker_link_consent_version,
        settings.broker_trading_consent_version,
        Decimal(settings.order_reference_commission_rate),
    )


def register(app: FastAPI) -> None:
    settings = cast(Settings, app.state.settings)
    clock = SystemClock()
    scope = Request({"type": "http", "app": app})

    def totp_service() -> OrderTotpService:
        if settings.totp_encryption_key is None:
            raise RuntimeError("Missing or invalid configuration: TOTP_ENCRYPTION_KEY")
        return OrderTotpService(
            identity.auth_uow,
            SecretCipher(settings.totp_encryption_key.get_secret_value()),
            TotpProvider(),
        )

    orders = InstalledOrderPorts(app)
    ctx = BrokerContext(
        broker_uow,
        BrokerDirectory(clock=clock),
        BrokerRequestReader(),
        LinkedAccountReader(),
        ControlsReader(AccountService(identity.account_uow)),
        TotpVerifier(totp_service, clock),
        QuoteReader(market_data.catalog_uow, lambda: market_data.quote_service(scope)),
        OrderCreation(orders),
        OrderQuery(orders),
        BrokersNotifier(market_data.directory_uow, market_data.notifier(scope)),
        clock,
        config(settings),
    )
    membership = BrokerLinkAdapter(clock=clock)
    app.state.order_broker_link = membership
    app.state.portfolio_broker_clients = membership
    app.state.associated_broker_reader = AssociatedBrokerReader(clock=clock)
    app.state.brokers_context = ctx
    app.state.brokers_expiry_service = ExpiryService(ctx)
    for module in (
        directory_router,
        links_router,
        proposals_router,
        broker_links_router,
        broker_proposals_router,
        broker_clients_router,
    ):
        app.include_router(module.router, prefix="/api/v1")


async def startup(app: FastAPI) -> None:
    for name, methods in {
        "order_proposal_creation": ("create",),
        "order_query_port": ("list_for_investor", "find_by_idempotency_key"),
    }.items():
        port = getattr(app.state, name, None)
        if port is None or any(not callable(getattr(port, method, None)) for method in methods):
            raise RuntimeError("Missing orders application port: " + name)
    app.state.brokers_expiry_job = None
    if app.state.settings.brokers_jobs_enabled.lower() == "true":
        job = ExpiryJob(
            app.state.brokers_expiry_service,
            int(app.state.settings.brokers_expiry_interval_seconds),
            "brokers-expiry",
        )
        app.state.brokers_expiry_job = job
        job.start()


async def shutdown(app: FastAPI) -> None:
    job = getattr(app.state, "brokers_expiry_job", None)
    if job is not None:
        await job.stop()
