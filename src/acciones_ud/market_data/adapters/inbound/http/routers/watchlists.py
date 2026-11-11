from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from acciones_ud.identity.adapters.inbound.http.deps import (
    require_permission,
    require_premium,
)
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.market_data.adapters.inbound.http.schemas.watchlists import (
    WatchlistIn,
    WatchlistOut,
    WatchlistSymbolIn,
)
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/watchlists", tags=["Watchlists"])

Manager = Annotated[CurrentUser, Depends(require_permission("watchlist:manage"))]
Premium = Annotated[CurrentUser, Depends(require_premium)]


@router.get("", response_model=list[WatchlistOut], responses=error_responses(401, 403))
async def list_watchlists(
    request: Request, user: Manager, premium: Premium
) -> list[WatchlistOut]:
    from acciones_ud.market_data.composition import watchlist_service

    items = await watchlist_service(request).list_watchlists(user.user_id)
    return [WatchlistOut.of(item) for item in items]


@router.post(
    "",
    status_code=201,
    response_model=WatchlistOut,
    responses=error_responses(401, 403, 422),
)
async def create_watchlist(
    request: Request, user: Manager, premium: Premium, body: WatchlistIn
) -> WatchlistOut:
    from acciones_ud.market_data.composition import watchlist_service

    return WatchlistOut.of(
        await watchlist_service(request).create(user.user_id, body.name)
    )


@router.get(
    "/{watchlist_id}",
    response_model=WatchlistOut,
    responses=error_responses(401, 403, 404, 422),
)
async def get_watchlist(
    request: Request, user: Manager, premium: Premium, watchlist_id: UUID
) -> WatchlistOut:
    from acciones_ud.market_data.composition import watchlist_service

    return WatchlistOut.of(
        await watchlist_service(request).get(user.user_id, watchlist_id)
    )


@router.post(
    "/{watchlist_id}/items",
    response_model=WatchlistOut,
    responses=error_responses(401, 403, 404, 409, 422),
)
async def add_symbol(
    request: Request,
    user: Manager,
    premium: Premium,
    watchlist_id: UUID,
    body: WatchlistSymbolIn,
) -> WatchlistOut:
    from acciones_ud.market_data.composition import watchlist_service

    return WatchlistOut.of(
        await watchlist_service(request).add_symbol(
            user.user_id, watchlist_id, body.symbol
        )
    )


@router.delete(
    "/{watchlist_id}/items/{symbol:path}",
    response_model=WatchlistOut,
    responses=error_responses(401, 403, 404, 422),
)
async def remove_symbol(
    request: Request,
    user: Manager,
    premium: Premium,
    watchlist_id: UUID,
    symbol: str,
) -> WatchlistOut:
    from acciones_ud.market_data.composition import watchlist_service

    return WatchlistOut.of(
        await watchlist_service(request).remove_symbol(
            user.user_id, watchlist_id, symbol
        )
    )
