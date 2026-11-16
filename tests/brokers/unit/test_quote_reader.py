from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from acciones_ud.brokers.adapters.outbound.market_data.quote_reader import QuoteReader
from acciones_ud.shared.domain.errors import AppError, ErrorCode


async def test_quote_reader_checks_active_and_tradable_and_preserves_database_errors():
    instrument = SimpleNamespace(status="active", tradable=True)

    @asynccontextmanager
    async def catalog():
        yield SimpleNamespace(instruments=SimpleNamespace(get=AsyncMock(return_value=instrument)))

    service = SimpleNamespace(
        quote=AsyncMock(
            return_value=SimpleNamespace(
                snapshot=SimpleNamespace(last_trade_price=Decimal("100.25"))
            )
        )
    )
    reader = QuoteReader(catalog, lambda: service)
    assert await reader.tradable("AAPL")
    instrument.status = "inactive"
    assert not await reader.tradable("AAPL")
    assert await reader.last_price("AAPL") == Decimal("100.25")
    service.quote.side_effect = AppError(502, ErrorCode.ALPACA_UNAVAILABLE, "Unavailable")
    assert await reader.last_price("AAPL") is None
    service.quote.side_effect = AppError(503, ErrorCode.DATABASE_UNAVAILABLE, "Unavailable")
    with pytest.raises(AppError) as caught:
        await reader.last_price("AAPL")
    assert caught.value.code == ErrorCode.DATABASE_UNAVAILABLE
