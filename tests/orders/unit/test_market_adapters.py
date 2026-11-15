from datetime import date, datetime, time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

from acciones_ud.orders.adapters.outbound.market_data.market_session import MarketSessionAdapter
from acciones_ud.orders.adapters.outbound.market_data.quote_reader import MarketQuoteReader
from acciones_ud.shared.domain.errors import AppError, ErrorCode


async def test_quote_unavailable_does_not_hide_database_failure() -> None:
    quote = AsyncMock()
    reader = MarketQuoteReader(lambda: quote)
    quote.quote.side_effect = AppError(502, ErrorCode.ALPACA_UNAVAILABLE, "Unavailable")
    assert await reader.current_price("AAPL") is None
    quote.quote.side_effect = AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Database unavailable")
    try:
        await reader.current_price("AAPL")
    except AppError as caught:
        assert caught.code == ErrorCode.DATABASE_UNAVAILABLE
    else:
        raise AssertionError("Database failure was hidden")


async def test_market_session_uses_effective_calendar() -> None:
    zone = ZoneInfo("America/New_York")
    opening = datetime.combine(date(2026, 11, 13), time(9, 30), zone)
    closing = datetime.combine(date(2026, 11, 13), time(16), zone)
    calendar = SimpleNamespace(
        calendar=AsyncMock(
            return_value=SimpleNamespace(days=[SimpleNamespace(open_at=opening, close_at=closing)])
        )
    )
    adapter = MarketSessionAdapter(lambda: calendar)
    assert await adapter.is_open("NASDAQ", opening)
    assert not await adapter.is_open("NASDAQ", closing)
    assert (await adapter.next_open("NASDAQ", opening)).closes_at == closing
