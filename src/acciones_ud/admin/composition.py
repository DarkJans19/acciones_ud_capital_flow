"""MOD-07 wiring; constructor paths never open a database connection."""

from decimal import Decimal
from typing import cast
from uuid import UUID

from fastapi import FastAPI

from acciones_ud.admin.adapters.inbound.http import (
    audit_router,
    commissions_router,
    compliance_router,
    fees_router,
    halts_router,
    kpis_router,
    markets_router,
)
from acciones_ud.admin.adapters.outbound.orders.platform_ledger import PlatformLedger
from acciones_ud.admin.adapters.outbound.orders.policy_adapters import (
    CommissionTermsAdapter,
    ProposalTermsAdapter,
    TradingGateAdapter,
)
from acciones_ud.admin.adapters.outbound.persistence.audit_trail_reader import AuditTrailReader
from acciones_ud.admin.adapters.outbound.persistence.unit_of_work import admin_uow
from acciones_ud.admin.adapters.outbound.portfolio.official_commission import OfficialCommission
from acciones_ud.admin.adapters.outbound.schedule_adapters import (
    OrderScheduleChanges,
    ScheduleListener,
    ScheduleNotifier,
)
from acciones_ud.admin.adapters.outbound.sources import KpiSource, MarketCatalog, UserReader
from acciones_ud.admin.application.commission_service import (
    CommissionQueryService,
    CommissionQuoteService,
)
from acciones_ud.admin.application.compliance_service import ComplianceService
from acciones_ud.admin.application.fee_service import FeeService
from acciones_ud.admin.application.halt_service import HaltService
from acciones_ud.admin.application.kpi_service import KpiService
from acciones_ud.admin.application.market_admin_view import MarketAdminView
from acciones_ud.admin.application.restriction_service import RestrictionService
from acciones_ud.admin.application.schedule_change_dispatcher import ScheduleChangeDispatcher
from acciones_ud.admin.application.step_up import StepUp
from acciones_ud.admin.domain.atypical import AtypicalConfig
from acciones_ud.admin.domain.ports import BrokerLinkPort
from acciones_ud.config.settings import invalid_admin_settings
from acciones_ud.identity import composition as identity
from acciones_ud.identity.adapters.outbound.security.cipher import SecretCipher
from acciones_ud.identity.adapters.outbound.security.totp import TotpProvider
from acciones_ud.identity.application.order_authorization import OrderTotpService
from acciones_ud.orders.adapters.outbound.identity.totp_verifier import IdentityTotpVerifier
from acciones_ud.orders.adapters.outbound.persistence.execution_repository import ledger_uow
from acciones_ud.orders.application.execution_ledger import ExecutionLedger
from acciones_ud.shared.domain.clock import SystemClock
from acciones_ud.shared.infrastructure.periodic_job import PeriodicJob


class InstalledLinks:
    def __init__(self, app: FastAPI) -> None:
        self.app = app

    @property
    def port(self) -> BrokerLinkPort:
        return cast(BrokerLinkPort, self.app.state.order_broker_link)

    async def linked_investors(self, broker_id: UUID) -> list[UUID]:
        return await self.port.linked_investors(broker_id)

    async def is_linked(self, broker_id: UUID, investor_id: UUID) -> bool:
        return await self.port.is_linked(broker_id, investor_id)


def register(app: FastAPI) -> None:
    settings, clock = app.state.settings, SystemClock()
    invalid = invalid_admin_settings(settings)
    if invalid:
        raise RuntimeError("Missing or invalid configuration: " + ", ".join(sorted(invalid)))
    markets, users, trail = MarketCatalog(clock), UserReader(), AuditTrailReader()
    ledger = PlatformLedger(ExecutionLedger(ledger_uow))

    def totp_service() -> OrderTotpService:
        return OrderTotpService(
            identity.auth_uow,
            SecretCipher(settings.totp_encryption_key.get_secret_value()),
            TotpProvider(),
        )

    step_up = StepUp(IdentityTotpVerifier(totp_service), clock)
    terms = CommissionTermsAdapter()
    app.state.order_commission_terms = terms
    app.state.order_trading_gate = TradingGateAdapter()
    app.state.portfolio_commission_port = OfficialCommission(
        Decimal(settings.order_reference_commission_rate)
    )
    app.state.brokers_commission_terms = ProposalTermsAdapter(markets, terms)
    app.state.admin_fees = FeeService(admin_uow, markets, step_up, clock)
    app.state.admin_halts = HaltService(admin_uow, markets, step_up, clock)
    app.state.admin_restrictions = RestrictionService(admin_uow, users, step_up, clock)
    app.state.admin_quote = CommissionQuoteService(admin_uow, markets, clock)
    app.state.admin_commissions = CommissionQueryService(ledger, InstalledLinks(app), users)
    app.state.admin_trail = trail
    app.state.admin_markets = MarketAdminView(admin_uow, markets, clock)
    app.state.admin_compliance = ComplianceService(
        admin_uow,
        ledger,
        trail,
        users,
        clock,
        AtypicalConfig(
            Decimal(settings.admin_atypical_absolute_usd),
            Decimal(settings.admin_atypical_multiplier),
            int(settings.admin_atypical_window_days),
            int(settings.admin_atypical_min_history),
            int(settings.admin_order_frequency_count),
            int(settings.admin_order_frequency_seconds),
            int(settings.admin_cancellation_count),
            int(settings.admin_cancellation_seconds),
            int(settings.admin_rejection_count),
            int(settings.admin_rejection_seconds),
        ),
    )
    app.state.admin_kpis = KpiService(
        admin_uow, KpiSource(), ledger, clock, int(settings.admin_kpi_cache_ttl_seconds)
    )
    dispatcher = ScheduleChangeDispatcher(
        admin_uow, OrderScheduleChanges(app), ScheduleNotifier(app), clock
    )
    listener = ScheduleListener(dispatcher)
    app.state.admin_dispatcher = dispatcher
    app.state.market_schedule_change_listener = listener
    app.state.admin_dispatch_tasks = listener.tasks
    for module in (
        fees_router,
        commissions_router,
        markets_router,
        halts_router,
        audit_router,
        compliance_router,
        kpis_router,
    ):
        app.include_router(module.router, prefix="/api/v1")


async def startup(app: FastAPI) -> None:
    for name, method in (
        ("order_schedule_change_port", "apply"),
        ("order_broker_link", "linked_investors"),
    ):
        if not callable(getattr(getattr(app.state, name, None), method, None)):
            raise RuntimeError("Missing administration integration port: " + name)
    app.state.admin_job = None
    if app.state.settings.admin_jobs_enabled.lower() == "true":
        job = PeriodicJob(
            app.state.admin_dispatcher,
            int(app.state.settings.admin_schedule_dispatch_interval_seconds),
            "admin-schedule-dispatch",
        )
        app.state.admin_job = job
        job.start()


async def shutdown(app: FastAPI) -> None:
    if getattr(app.state, "admin_job", None):
        await app.state.admin_job.stop()
    await app.state.market_schedule_change_listener.stop()
