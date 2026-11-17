from datetime import date
from typing import Annotated, cast

from fastapi import Depends, Query, Request

from acciones_ud.identity.adapters.inbound.http.deps import get_current_user
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.portfolio.application.portfolio_service import PortfolioService
from acciones_ud.portfolio.application.report_service import ReportService
from acciones_ud.portfolio.application.risk_profile_service import RiskProfileService
from acciones_ud.portfolio.application.statistics_service import StatisticsService
from acciones_ud.portfolio.domain.access import resolve
from acciones_ud.portfolio.domain.model import Period
from acciones_ud.portfolio.domain.period import parse


async def require_investor(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    resolve(user, "investor")
    return user


async def require_broker(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
    resolve(user, "broker")
    return user


def period_query(
    from_: Annotated[
        date,
        Query(
            alias="from",
            description="Fecha inicial inclusiva, formato YYYY-MM-DD.",
            examples=["2026-11-01"],
        ),
    ],
    to: Annotated[
        date,
        Query(description="Fecha final inclusiva, formato YYYY-MM-DD.", examples=["2026-11-16"]),
    ],
) -> Period:
    return parse(from_, to)


Investor = Annotated[CurrentUser, Depends(require_investor)]
Broker = Annotated[CurrentUser, Depends(require_broker)]
PeriodQuery = Annotated[Period, Depends(period_query)]


def portfolio(request: Request) -> PortfolioService:
    return cast(PortfolioService, request.app.state.portfolio_service)


def reports(request: Request) -> ReportService:
    return cast(ReportService, request.app.state.portfolio_report_service)


def statistics(request: Request) -> StatisticsService:
    return cast(StatisticsService, request.app.state.portfolio_statistics_service)


def risk(request: Request) -> RiskProfileService:
    return cast(RiskProfileService, request.app.state.portfolio_risk_service)
