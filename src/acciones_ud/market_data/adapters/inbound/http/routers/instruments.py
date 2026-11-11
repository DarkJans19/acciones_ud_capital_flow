from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from acciones_ud.identity.adapters.inbound.http.deps import require_permission
from acciones_ud.identity.domain.models import CurrentUser
from acciones_ud.market_data.adapters.inbound.http.schemas.instruments import (
    AssetDetailOut,
    CandlesOut,
    DepthOut,
    InstrumentOut,
    QuoteOut,
    SearchOut,
)
from acciones_ud.shared.infrastructure.http_errors import error_responses

router = APIRouter(prefix="/instruments", tags=["Instruments"])

MarketReader = Annotated[CurrentUser, Depends(require_permission("market:read"))]


@router.get(
    "/search",
    response_model=SearchOut,
    responses=error_responses(401, 403, 422, 502, 503),
)
async def search(
    request: Request,
    user: MarketReader,
    q: str = Query(description="Symbol prefix or name fragment, trimmed 1-50 characters."),
    page: int = Query(1, ge=1),
    exchange: str | None = Query(None),
    classification: str | None = Query(None, pattern="^(tradable|view_only)$"),
) -> SearchOut:
    from acciones_ud.market_data.composition import search_service

    results, total, page_size = await search_service(request).search(
        q, exchange, classification, page
    )
    return SearchOut(
        page=page,
        page_size=page_size,
        total=total,
        results=[InstrumentOut.of(item) for item in results],
    )


@router.get(
    "/{symbol:path}/quote",
    response_model=QuoteOut,
    responses=error_responses(401, 403, 404, 422, 502, 503),
)
async def quote(request: Request, user: MarketReader, symbol: str) -> QuoteOut:
    from acciones_ud.market_data.composition import quote_service

    return QuoteOut.of(await quote_service(request).quote(symbol))


@router.get(
    "/{symbol:path}/candles",
    response_model=CandlesOut,
    responses=error_responses(401, 403, 404, 422, 502, 503),
)
async def candles(
    request: Request,
    user: MarketReader,
    symbol: str,
    timeframe: str = Query(description="1Min, 5Min, 15Min, 1Hour or 1Day."),
    start: str = Query(description="ISO 8601 date or datetime."),
    end: str = Query(description="ISO 8601 date or datetime; a date means its end (UTC)."),
    page_size: int = Query(1000, ge=1, le=10000),
    page_token: str | None = Query(None),
) -> CandlesOut:
    from acciones_ud.market_data.composition import candle_service

    view = await candle_service(request).candles(
        symbol, timeframe, start, end, page_size, page_token
    )
    return CandlesOut.of(view)


@router.get(
    "/{symbol:path}/depth",
    response_model=DepthOut,
    responses=error_responses(401, 403, 404, 422, 502, 503),
)
async def depth(request: Request, user: MarketReader, symbol: str) -> DepthOut:
    from acciones_ud.market_data.composition import depth_service

    return DepthOut.of(await depth_service(request).depth(symbol))


@router.get(
    "/{symbol:path}",
    response_model=AssetDetailOut,
    responses=error_responses(401, 403, 404, 422, 500, 502, 503),
)
async def detail(request: Request, user: MarketReader, symbol: str) -> AssetDetailOut:
    from acciones_ud.market_data.composition import asset_detail_service

    return AssetDetailOut.of(await asset_detail_service(request).detail(symbol))
