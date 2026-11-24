from fastapi import APIRouter, Request

from acciones_ud.admin.adapters.inbound.http import schemas as s
from acciones_ud.admin.adapters.inbound.http.commissions_router import From, Size, To
from acciones_ud.admin.adapters.inbound.http.deps import AuditRoute, MarketsAdmin
from acciones_ud.admin.domain.periods import Period
from acciones_ud.admin.domain.reports import canonical_value
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(
    prefix="/admin/markets",
    tags=["admin-markets"],
    route_class=AuditRoute,
    responses=error_responses(401, 403, 404, 422, 503),
)


@router.get("", response_model=list[s.AdminMarketOut])
async def markets(request: Request, user: MarketsAdmin) -> object:
    return canonical_value(await request.app.state.admin_markets.list())


@router.get("/{market_code}/schedule-changes", response_model=s.AdminPageOut[s.ScheduleChangeOut])
async def changes(
    market_code: str,
    request: Request,
    user: MarketsAdmin,
    from_: From,
    to: To,
    cursor: str | None = None,
    page_size: Size = 20,
) -> object:
    await request.app.state.admin_markets.list(market_code)
    return canonical_value(
        await request.app.state.admin_dispatcher.history(
            market_code, Period(from_, to), cursor, page_size
        )
    )


@router.get("/{market_code}", response_model=s.AdminMarketOut)
async def market(market_code: str, request: Request, user: MarketsAdmin) -> object:
    values = await request.app.state.admin_markets.list(market_code)
    return canonical_value(values[0])
