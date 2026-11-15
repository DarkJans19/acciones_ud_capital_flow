from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import httpx

from acciones_ud.shared.domain.alpaca_errors import AlpacaUnavailable, classify
from acciones_ud.shared.infrastructure.alpaca_http import raise_for_alpaca


class AlpacaPositionsClient:
    def __init__(self, client: httpx.AsyncClient | Callable[[], httpx.AsyncClient]) -> None:
        self._client = client

    async def qty_available(self, alpaca_account_id: str, symbol: str) -> Decimal:
        client = self._client() if callable(self._client) else self._client
        try:
            response = await client.get(
                f"/v1/trading/accounts/{alpaca_account_id}/positions/{quote(symbol, safe='')}",
                timeout=4,
            )
        except httpx.HTTPError as exc:
            raise classify(exc) from None
        if response.status_code == 404:
            return Decimal(0)
        raise_for_alpaca(response)
        try:
            value = Decimal(response.json()["qty_available"])
            if not value.is_finite():
                raise ValueError()
            return value
        except (InvalidOperation, ValueError, KeyError, TypeError):
            raise AlpacaUnavailable() from None
