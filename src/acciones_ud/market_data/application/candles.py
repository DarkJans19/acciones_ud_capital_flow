"""RF-25: historical bars with validation, mapping and freshness metadata."""

from dataclasses import dataclass

from acciones_ud.market_data.domain.bars import map_bars, validate_bars_request
from acciones_ud.market_data.domain.entities import Bar
from acciones_ud.market_data.domain.freshness import CandleMeta, candle_meta
from acciones_ud.market_data.domain.ports import AlpacaDataPort, QuoteWorkFactory
from acciones_ud.market_data.domain.symbols import validate_symbol
from acciones_ud.shared.domain.errors import AppError, ErrorCode


@dataclass(frozen=True)
class CandleView:
    symbol: str
    timeframe: str
    bars: list[Bar]
    next_page_token: str | None
    meta: CandleMeta


class CandleService:
    def __init__(self, uow: QuoteWorkFactory, data: AlpacaDataPort, feed: str) -> None:
        self.uow = uow
        self.data = data
        self.feed = feed

    async def candles(
        self,
        raw_symbol: str,
        timeframe: str,
        start: str,
        end: str,
        page_size: int,
        page_token: str | None,
    ) -> CandleView:
        symbol = validate_symbol(raw_symbol)
        start_at, end_at = validate_bars_request(timeframe, start, end, page_size)
        async with self.uow() as work:
            instrument = await work.instruments.get(symbol)
        if instrument is None:
            raise AppError(404, ErrorCode.SYMBOL_NOT_FOUND, "Symbol not found.")

        page = await self.data.bars(
            symbol, timeframe, start_at, end_at, page_size, page_token
        )
        mapped = map_bars(page.bars, start_at, end_at, page_size, page.next_page_token)
        return CandleView(
            symbol=symbol,
            timeframe=timeframe,
            bars=mapped.bars,
            next_page_token=mapped.next_page_token,
            meta=candle_meta(instrument.asset_class, self.feed),
        )
