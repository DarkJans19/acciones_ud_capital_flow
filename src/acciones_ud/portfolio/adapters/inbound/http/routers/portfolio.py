from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from acciones_ud.portfolio.adapters.inbound.http import deps
from acciones_ud.portfolio.adapters.inbound.http.deps import Investor, PeriodQuery
from acciones_ud.portfolio.adapters.inbound.http.schemas.executions import ExecutionPage
from acciones_ud.portfolio.adapters.inbound.http.schemas.pagination import Cursor, PageSize
from acciones_ud.portfolio.adapters.inbound.http.schemas.positions import PositionsResponse
from acciones_ud.portfolio.adapters.inbound.http.schemas.reports import (
    PeriodInput,
    ReportPage,
    ReportResponse,
)
from acciones_ud.portfolio.adapters.inbound.http.schemas.risk_profile import RiskProfileResponse
from acciones_ud.portfolio.adapters.inbound.http.schemas.statistics import StatisticsResponse
from acciones_ud.portfolio.domain.model import ReportType
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/portfolio", tags=["portfolio"], responses=error_responses(422))


@router.get(
    "/positions",
    response_model=PositionsResponse,
    responses=error_responses(401, 403, 409, 502, 503),
)
async def positions(request: Request, user: Investor) -> object:
    return await deps.portfolio(request).positions(user.user_id)


@router.get(
    "/executions", response_model=ExecutionPage, responses=error_responses(401, 403, 422, 503)
)
async def executions(
    request: Request,
    user: Investor,
    period: PeriodQuery,
    symbol: Annotated[str | None, Query(pattern=r"^[A-Za-z0-9./-]{1,32}$")] = None,
    cursor: Cursor = None,
    page_size: PageSize = 50,
) -> object:
    return await deps.portfolio(request).executions(
        user.user_id, period, symbol.upper() if symbol else None, cursor, page_size
    )


@router.get(
    "/statistics", response_model=StatisticsResponse, responses=error_responses(401, 403, 422, 503)
)
async def statistics(request: Request, user: Investor, period: PeriodQuery) -> object:
    return await deps.statistics(request).statistics(user.user_id, period)


@router.get(
    "/risk-profile",
    response_model=RiskProfileResponse,
    responses=error_responses(401, 403, 409, 502, 503),
)
async def risk_profile(request: Request, user: Investor) -> object:
    return await deps.risk(request).profile(user.user_id)


@router.post(
    "/reports",
    response_model=ReportResponse,
    status_code=201,
    responses=error_responses(401, 403, 409, 422, 502, 503),
)
async def create_report(request: Request, user: Investor, body: PeriodInput) -> object:
    return await deps.reports(request).create_on_demand(user.user_id, body.period())


@router.get(
    "/reports", response_model=ReportPage, responses=error_responses(401, 403, 409, 422, 503)
)
async def reports(
    request: Request,
    user: Investor,
    type: ReportType | None = None,
    cursor: Cursor = None,
    page_size: PageSize = 50,
) -> object:
    return await deps.reports(request).list(user.user_id, type, cursor, page_size)


@router.get(
    "/reports/{report_id}",
    response_model=ReportResponse,
    responses=error_responses(401, 403, 404, 409, 503),
)
async def report(request: Request, user: Investor, report_id: UUID) -> object:
    return await deps.reports(request).get(user.user_id, report_id)
