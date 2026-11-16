from collections.abc import Callable
from decimal import Decimal

from acciones_ud.market_data.application.quotes import QuoteService
from acciones_ud.market_data.domain.ports import CatalogWorkFactory
from acciones_ud.shared.domain.errors import AppError, ErrorCode


class QuoteReader:
    def __init__(self, catalog: CatalogWorkFactory, service: Callable[[], QuoteService]) -> None:
        self.catalog, self.service = catalog, service

    async def tradable(self, symbol: str) -> bool:
        async with self.catalog() as work:
            instrument = await work.instruments.get(symbol)
        return bool(instrument and instrument.status == "active" and instrument.tradable)

    async def last_price(self, symbol: str) -> Decimal | None:
        try:
            view = await self.service().quote(symbol)
        except AppError as exc:
            if exc.code in {
                ErrorCode.ALPACA_UNAVAILABLE,
                ErrorCode.ALPACA_RATE_LIMITED,
                ErrorCode.SYMBOL_NOT_FOUND,
            }:
                return None
            raise
        price = view.snapshot.last_trade_price
        return price if price is not None and price.is_finite() and price > 0 else None
