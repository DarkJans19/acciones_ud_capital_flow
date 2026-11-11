from datetime import date
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi import status as http_status

from acciones_ud.identity.adapters.inbound.http.deps import require_permission
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.market_data.adapters.inbound.http.schemas.markets import (
    DefaultScheduleIn,
    DefaultScheduleOut,
    ScheduleOverrideIn,
    ScheduleOverrideOut,
    ScheduleOverrideUpdateIn,
)
from acciones_ud.shared.domain.errors import AppError, ErrorCode
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/admin/markets", tags=["Markets administration"])

MarketAdmin = Annotated[CurrentUser, Depends(require_permission("admin:markets"))]


def parse_override_id(raw: str) -> UUID:
    try:
        return UUID(raw)
    except ValueError:
        raise AppError(
            404, ErrorCode.NOT_FOUND, "Override not found.", {"resource": "override"}
        ) from None


@router.put(
    "/{market_code}/default-schedule",
    response_model=DefaultScheduleOut,
    responses=error_responses(401, 403, 404, 422),
)
async def set_default_schedule(
    request: Request, user: MarketAdmin, market_code: str, body: DefaultScheduleIn
) -> DefaultScheduleOut:
    from acciones_ud.market_data.composition import schedule_admin_service

    market = await schedule_admin_service(request).set_default(
        market_code, body.open_time, body.close_time
    )
    return DefaultScheduleOut(
        market=market.code,
        open_time=body.open_time,
        close_time=body.close_time,
    )


@router.delete(
    "/{market_code}/default-schedule",
    status_code=http_status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 403, 404, 422),
)
async def clear_default_schedule(
    request: Request, user: MarketAdmin, market_code: str
) -> Response:
    from acciones_ud.market_data.composition import schedule_admin_service

    await schedule_admin_service(request).clear_default(market_code)
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)


@router.get(
    "/{market_code}/schedule-overrides",
    response_model=list[ScheduleOverrideOut],
    responses=error_responses(401, 403, 404, 422),
)
async def list_overrides(
    request: Request,
    user: MarketAdmin,
    market_code: str,
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
) -> list[ScheduleOverrideOut]:
    from acciones_ud.market_data.composition import schedule_admin_service

    overrides = await schedule_admin_service(request).list_overrides(
        market_code, start, end
    )
    return [ScheduleOverrideOut.of(override) for override in overrides]


@router.post(
    "/{market_code}/schedule-overrides",
    status_code=http_status.HTTP_201_CREATED,
    response_model=ScheduleOverrideOut,
    responses=error_responses(401, 403, 404, 409, 422),
)
async def create_override(
    request: Request, user: MarketAdmin, market_code: str, body: ScheduleOverrideIn
) -> ScheduleOverrideOut:
    from acciones_ud.market_data.composition import schedule_admin_service

    override = await schedule_admin_service(request).create_override(
        market_code,
        uuid4(),
        body.date,
        body.closed,
        body.open_time,
        body.close_time,
    )
    return ScheduleOverrideOut.of(override)


@router.put(
    "/{market_code}/schedule-overrides/{override_id}",
    response_model=ScheduleOverrideOut,
    responses=error_responses(401, 403, 404, 422),
)
async def update_override(
    request: Request,
    user: MarketAdmin,
    market_code: str,
    override_id: str,
    body: ScheduleOverrideUpdateIn,
) -> ScheduleOverrideOut:
    from acciones_ud.market_data.composition import schedule_admin_service

    override = await schedule_admin_service(request).update_override(
        market_code,
        parse_override_id(override_id),
        body.closed,
        body.open_time,
        body.close_time,
    )
    return ScheduleOverrideOut.of(override)


@router.delete(
    "/{market_code}/schedule-overrides/{override_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 403, 404, 422),
)
async def delete_override(
    request: Request, user: MarketAdmin, market_code: str, override_id: str
) -> Response:
    from acciones_ud.market_data.composition import schedule_admin_service

    await schedule_admin_service(request).delete_override(
        market_code, parse_override_id(override_id)
    )
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
