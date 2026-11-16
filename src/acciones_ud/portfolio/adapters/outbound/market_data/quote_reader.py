from decimal import Decimal

from acciones_ud.orders.adapters.outbound.market_data.quote_reader import MarketQuoteReader


class QuoteReader(MarketQuoteReader):
    async def last_price(self, symbol: str) -> Decimal | None:
        return await self.current_price(symbol)
