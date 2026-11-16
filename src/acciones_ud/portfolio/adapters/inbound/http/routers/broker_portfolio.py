from uuid import UUID

from fastapi import APIRouter, Request

from acciones_ud.portfolio.adapters.inbound.http import deps
from acciones_ud.portfolio.adapters.inbound.http.deps import Broker
from acciones_ud.portfolio.adapters.inbound.http.schemas.pagination import Cursor, PageSize
from acciones_ud.portfolio.adapters.inbound.http.schemas.positions import PositionsResponse
from acciones_ud.portfolio.adapters.inbound.http.schemas.reports import (
    PeriodInput,
    ReportPage,
    ReportResponse,
)
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(
    prefix="/portfolio/broker", tags=["broker-portfolio"], responses=error_responses(422)
)


@router.post(
    "/reports",
    response_model=ReportResponse,
    status_code=201,
    responses=error_responses(401, 403, 422, 502, 503),
)
async def create_report(request: Request, user: Broker, body: PeriodInput) -> object:
    return await deps.reports(request).create_broker(user.user_id, body.period())


@router.get("/reports", response_model=ReportPage, responses=error_responses(401, 403, 503))
async def reports(
    request: Request, user: Broker, cursor: Cursor = None, page_size: PageSize = 50
) -> object:
    return await deps.reports(request).list(
        user.user_id, "broker", cursor, page_size, require_linked=False
    )


@router.get(
    "/reports/{report_id}",
    response_model=ReportResponse,
    responses=error_responses(401, 403, 404, 503),
)
async def report(request: Request, user: Broker, report_id: UUID) -> object:
    return await deps.reports(request).get(user.user_id, report_id, require_linked=False)


@router.get(
    "/clients/{investor_id}/positions",
    response_model=PositionsResponse,
    responses=error_responses(401, 403, 404, 502, 503),
)
async def client_positions(request: Request, user: Broker, investor_id: UUID) -> object:
    return await deps.portfolio(request).client_positions(user.user_id, investor_id)


@router.get(
    "/clients/{investor_id}/reports/{report_id}",
    response_model=ReportResponse,
    responses=error_responses(401, 403, 404, 503),
)
async def client_report(
    request: Request, user: Broker, investor_id: UUID, report_id: UUID
) -> object:
    return await deps.reports(request).get_client_report(user.user_id, investor_id, report_id)
