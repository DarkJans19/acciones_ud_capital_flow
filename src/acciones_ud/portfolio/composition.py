"""MOD-05 composition; provider and database connections remain lazy."""

from decimal import Decimal, InvalidOperation
from typing import cast
from uuid import UUID

from fastapi import FastAPI, Request

from acciones_ud.identity import composition as identity
from acciones_ud.identity.application.account import AccountService
from acciones_ud.market_data import composition as market_data
from acciones_ud.orders.adapters.outbound.persistence.execution_repository import ledger_uow
from acciones_ud.orders.application.execution_ledger import ExecutionLedger
from acciones_ud.portfolio.adapters.inbound.http.routers import broker_portfolio, portfolio
from acciones_ud.portfolio.adapters.inbound.jobs.report_scheduler_job import ReportSchedulerJob
from acciones_ud.portfolio.adapters.outbound.alpaca.positions_client import AlpacaPositionsClient
from acciones_ud.portfolio.adapters.outbound.brokers.null_broker_client import NullBrokerClient
from acciones_ud.portfolio.adapters.outbound.commissions.reference_commission import (
    ReferenceCommission,
)
from acciones_ud.portfolio.adapters.outbound.identity.account_reader import AccountReader
from acciones_ud.portfolio.adapters.outbound.identity.report_preferences_reader import (
    ReportPreferencesReader,
)
from acciones_ud.portfolio.adapters.outbound.identity.view_settings_reader import ViewSettingsReader
from acciones_ud.portfolio.adapters.outbound.market_data.instrument_reader import InstrumentReader
from acciones_ud.portfolio.adapters.outbound.market_data.quote_reader import QuoteReader
from acciones_ud.portfolio.adapters.outbound.market_data.report_notifier import ReportNotifier
from acciones_ud.portfolio.adapters.outbound.market_data.session_reader import SessionReader
from acciones_ud.portfolio.adapters.outbound.orders.execution_reader import ExecutionReader
from acciones_ud.portfolio.adapters.outbound.orders.reservation_reader import ReservationReader
from acciones_ud.portfolio.adapters.outbound.persistence.unit_of_work import report_uow
from acciones_ud.portfolio.adapters.outbound.wallet.equity_reader import EquityReader
from acciones_ud.portfolio.application.portfolio_service import PortfolioService
from acciones_ud.portfolio.application.position_port import PortfolioPositionPort
from acciones_ud.portfolio.application.report_builder import ReportBuilder
from acciones_ud.portfolio.application.report_scheduler import ReportScheduler
from acciones_ud.portfolio.application.report_service import ReportService
from acciones_ud.portfolio.application.risk_profile_service import RiskProfileService
from acciones_ud.portfolio.application.statistics_service import StatisticsService
from acciones_ud.portfolio.domain import model as m
from acciones_ud.portfolio.domain.ports import BrokerClientPort, CommissionPort
from acciones_ud.shared.domain.clock import SystemClock


class InstalledCommission:
    def __init__(self, app: FastAPI, default: CommissionPort) -> None:
        self.app, self.default = app, default

    def commission(self, execution: m.ExecutionRecord) -> m.CommissionQuote:
        port = cast(
            CommissionPort, getattr(self.app.state, "portfolio_commission_port", self.default)
        )
        return port.commission(execution)


class InstalledBrokerClients:
    def __init__(self, app: FastAPI) -> None:
        self.app, self.default = app, NullBrokerClient()

    @property
    def port(self) -> BrokerClientPort:
        return cast(
            BrokerClientPort, getattr(self.app.state, "portfolio_broker_clients", self.default)
        )

    async def linked_investors(self, broker_id: UUID) -> list[UUID]:
        return await self.port.linked_investors(broker_id)

    async def is_linked(self, broker_id: UUID, investor_id: UUID) -> bool:
        return await self.port.is_linked(broker_id, investor_id)


def register(app: FastAPI) -> None:
    settings, clock = app.state.settings, SystemClock()
    scope = Request({"type": "http", "app": app})
    try:
        rate = Decimal(settings.order_reference_commission_rate)
        if not rate.is_finite():
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise RuntimeError(
            "Missing or invalid configuration: ORDER_REFERENCE_COMMISSION_RATE"
        ) from None
    try:
        window = int(settings.portfolio_risk_window_days)
    except (ValueError, TypeError):
        raise RuntimeError("Missing or invalid configuration: PORTFOLIO_RISK_WINDOW_DAYS") from None
    commissions = InstalledCommission(app, ReferenceCommission(rate))
    brokers = InstalledBrokerClients(app)
    positions = AlpacaPositionsClient(lambda: app.state.alpaca_broker)
    ledger = ExecutionLedger(ledger_uow)
    executions = ExecutionReader(ledger)
    instruments = InstrumentReader(market_data.catalog_uow)
    service = PortfolioService(
        AccountReader(identity.kyc_uow),
        positions,
        executions,
        ReservationReader(ledger),
        QuoteReader(lambda: market_data.quote_service(scope)),
        instruments,
        ViewSettingsReader(AccountService(identity.account_uow)),
        commissions,
        brokers,
        clock,
    )
    reports = ReportService(
        ReportBuilder(service, executions, commissions), report_uow, brokers, clock
    )
    app.state.order_position_port = PortfolioPositionPort(positions)
    app.state.portfolio_service = service
    app.state.portfolio_statistics_service = StatisticsService(executions, instruments)
    app.state.portfolio_risk_service = RiskProfileService(
        service, executions, instruments, EquityReader(app.state.wallet_service), clock, window
    )
    app.state.portfolio_report_service = reports
    app.state.portfolio_report_scheduler = ReportScheduler(
        reports,
        ReportPreferencesReader(clock),
        SessionReader(lambda: market_data.calendar_service(scope)),
        ReportNotifier(market_data.directory_uow, market_data.notifier(scope)),
        clock,
    )
    for router in (portfolio.router, broker_portfolio.router):
        app.include_router(router, prefix="/api/v1")


async def startup(app: FastAPI) -> None:
    app.state.portfolio_job = None
    if app.state.settings.portfolio_jobs_enabled.lower() == "true":
        job = ReportSchedulerJob(
            app.state.portfolio_report_scheduler,
            int(app.state.settings.portfolio_report_interval_seconds),
            "portfolio-reports",
        )
        app.state.portfolio_job = job
        job.start()


async def shutdown(app: FastAPI) -> None:
    job = getattr(app.state, "portfolio_job", None)
    if job is not None:
        await job.stop()
