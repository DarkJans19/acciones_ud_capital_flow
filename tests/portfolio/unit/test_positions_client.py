from decimal import Decimal

import httpx
import pytest

from acciones_ud.portfolio.adapters.outbound.alpaca.positions_client import AlpacaPositionsClient
from acciones_ud.shared.domain.alpaca_errors import AlpacaRateLimited, AlpacaUnavailable


@pytest.mark.parametrize("status,error", [(429, AlpacaRateLimited), (500, AlpacaUnavailable)])
async def test_classified_errors(status, error):
    async with httpx.AsyncClient(
        base_url="https://alpaca.test",
        transport=httpx.MockTransport(lambda r: httpx.Response(status)),
    ) as client:
        port = AlpacaPositionsClient(client)
        with pytest.raises(error):
            await port.list("account")


async def test_mapping_and_absent_position():
    raw = dict(
        symbol="AAPL",
        exchange="NASDAQ",
        qty="2",
        qty_available="1.25",
        avg_entry_price="10.00",
        current_price="12.00",
    )

    def handler(request):
        if request.url.path.endswith("/positions"):
            return httpx.Response(200, json=[raw])
        return httpx.Response(404)

    async with httpx.AsyncClient(
        base_url="https://alpaca.test", transport=httpx.MockTransport(handler)
    ) as client:
        port = AlpacaPositionsClient(client)
        assert (await port.list("account"))[0].qty_available == Decimal("1.25")
        assert await port.get("account", "ABSENT") is None
