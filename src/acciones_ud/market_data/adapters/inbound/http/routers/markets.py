from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from acciones_ud.identity.adapters.inbound.http.deps import require_permission
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.market_data.adapters.inbound.http.schemas.instruments import MarketOut
from acciones_ud.market_data.adapters.inbound.http.schemas.markets import (
    CalendarOut,
    ClockOut,
    MarketStatusOut,
)
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/markets", tags=["Markets"])

MarketReader = Annotated[CurrentUser, Depends(require_permission("market:read"))]
StartDate = Annotated[date, Query(description="First date (YYYY-MM-DD).")]
EndDate = Annotated[
    date, Query(description="Last date (YYYY-MM-DD), at most 366 days after start.")
]
TimeZone = Annotated[
    str | None, Query(description="IANA time zone, defaults to America/New_York.")
]


@router.get("", response_model=list[MarketOut], responses=error_responses(401, 403, 502, 503))
async def list_markets(request: Request, user: MarketReader) -> list[MarketOut]:
    from acciones_ud.market_data.composition import exchanges_service

    return [MarketOut.of(market) for market in await exchanges_service(request).list_markets()]


@router.get(
    "/calendar",
    response_model=CalendarOut,
    responses=error_responses(401, 403, 404, 422, 502, 503),
)
async def calendar(
    request: Request,
    user: MarketReader,
    start: StartDate,
    end: EndDate,
    tz: TimeZone = None,
    market: Annotated[str | None, Query()] = None,
) -> CalendarOut:
    from acciones_ud.market_data.composition import calendar_service

    return CalendarOut.of(
        await calendar_service(request).calendar(market, start, end, tz)
    )


@router.get(
    "/clock", response_model=ClockOut, responses=error_responses(401, 403, 422, 502, 503)
)
async def clock(
    request: Request,
    user: MarketReader,
    tz: TimeZone = None,
) -> ClockOut:
    from acciones_ud.market_data.composition import clock_service

    return ClockOut.of(await clock_service(request).clock(tz))


@router.get(
    "/{market_code}/status",
    response_model=MarketStatusOut,
    responses=error_responses(401, 403, 404, 422, 502, 503),
)
async def status(
    request: Request,
    user: MarketReader,
    market_code: str,
    day: Annotated[date, Query(alias="date", description="Date to inspect (YYYY-MM-DD).")],
    tz: TimeZone = None,
) -> MarketStatusOut:
    from acciones_ud.market_data.composition import market_status_service

    return MarketStatusOut.of(
        await market_status_service(request).status(market_code, day, tz)
    )
