"""RF-25: depth use case. Never fabricates levels and never falls back to cache."""

from dataclasses import dataclass

from acciones_ud.market_data.domain.depth import from_latest_quote
from acciones_ud.market_data.domain.entities import DepthResult, Freshness
from acciones_ud.market_data.domain.freshness import annotate
from acciones_ud.market_data.domain.ports import AlpacaDataPort, QuoteWorkFactory
from acciones_ud.market_data.domain.symbols import validate_symbol
from acciones_ud.shared.domain.alpaca_errors import AlpacaError, to_app_error
from acciones_ud.shared.domain.clock import Clock
from acciones_ud.shared.domain.errors import AppError, ErrorCode


@dataclass(frozen=True)
class DepthView:
    symbol: str
    result: DepthResult
    freshness: Freshness


class DepthService:
    def __init__(
        self,
        uow: QuoteWorkFactory,
        data: AlpacaDataPort,
        clock: Clock,
        feed: str,
        threshold_seconds: int,
    ) -> None:
        self.uow = uow
        self.data = data
        self.clock = clock
        self.feed = feed
        self.threshold_seconds = threshold_seconds

    async def depth(self, raw_symbol: str) -> DepthView:
        symbol = validate_symbol(raw_symbol)
        async with self.uow() as work:
            instrument = await work.instruments.get(symbol)
        if instrument is None:
            raise AppError(404, ErrorCode.SYMBOL_NOT_FOUND, "Symbol not found.")
        try:
            document = await self.data.latest_quote(symbol)
        except AlpacaError as exc:
            raise to_app_error(exc) from None
        result = from_latest_quote(document)
        freshness = annotate(
            instrument.asset_class,
            self.feed,
            result.as_of,
            self.clock.now(),
            self.threshold_seconds,
            served_from_cache=False,
        )
        return DepthView(symbol=symbol, result=result, freshness=freshness)
