from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI

from acciones_ud.portfolio.adapters.inbound.http.routers import broker_portfolio, portfolio
from acciones_ud.portfolio.application.risk_profile_service import RiskProfileService
from acciones_ud.portfolio.application.statistics_service import StatisticsService
from acciones_ud.shared.infrastructure.http_errors import register_exception_handlers
from tests.portfolio.unit.test_reports import reporting


def api_for(settings):
    service, source, alpaca, repo = reporting()
    app = FastAPI()
    app.state.settings = settings
    ps = service.builder.portfolio
    app.state.portfolio_service = ps
    app.state.portfolio_report_service = service
    app.state.portfolio_statistics_service = StatisticsService(source, source)
    app.state.portfolio_risk_service = RiskProfileService(
        ps,
        source,
        source,
        SimpleNamespace(equity=AsyncMock(return_value=Decimal(100))),
        ps.clock,
        90,
    )
    register_exception_handlers(app)
    for router in (portfolio.router, broker_portfolio.router):
        app.include_router(router, prefix="/api/v1")
    return app, source, alpaca, repo
