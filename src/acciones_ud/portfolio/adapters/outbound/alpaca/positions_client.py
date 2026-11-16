from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

import httpx

from acciones_ud.portfolio.domain.model import RawPosition
from acciones_ud.shared.domain.alpaca_errors import AlpacaUnavailable, classify
from acciones_ud.shared.infrastructure.alpaca_http import raise_for_alpaca


def position(raw: Any) -> RawPosition:
    try:
        values = [
            Decimal(raw[name])
            for name in ("qty", "qty_available", "avg_entry_price", "current_price")
        ]
        if not all(value.is_finite() for value in values):
            raise ValueError()
        symbol, exchange = raw["symbol"], raw["exchange"]
        if not isinstance(symbol, str) or not symbol or not isinstance(exchange, str):
            raise ValueError()
        return RawPosition(symbol, exchange, *values)
    except (InvalidOperation, ValueError, KeyError, TypeError):
        raise AlpacaUnavailable() from None


class AlpacaPositionsClient:
    def __init__(self, client: httpx.AsyncClient | Callable[[], httpx.AsyncClient]) -> None:
        self.client = client

    async def _request(self, path: str) -> httpx.Response:
        client = self.client() if callable(self.client) else self.client
        try:
            return await client.get(path, timeout=4)
        except httpx.HTTPError as exc:
            raise classify(exc) from None

    async def list(self, alpaca_account_id: str) -> list[RawPosition]:
        response = await self._request(
            f"/v1/trading/accounts/{quote(alpaca_account_id, safe='')}/positions"
        )
        raise_for_alpaca(response)
        try:
            rows = response.json()
            if not isinstance(rows, list):
                raise ValueError()
            return [position(raw) for raw in rows]
        except ValueError:
            raise AlpacaUnavailable() from None

    async def get(self, alpaca_account_id: str, symbol: str) -> RawPosition | None:
        response = await self._request(
            f"/v1/trading/accounts/{quote(alpaca_account_id, safe='')}/positions/"
            f"{quote(symbol, safe='')}"
        )
        if response.status_code == 404:
            return None
        raise_for_alpaca(response)
        try:
            return position(response.json())
        except ValueError:
            raise AlpacaUnavailable() from None
