"""Alpaca Market Data REST client: snapshots, bars and latest quotes (RF-25)."""

from datetime import datetime
from decimal import Decimal
from typing import Any, cast

import httpx

from acciones_ud.market_data.domain.entities import (
    Bar,
    BarsPage,
    LatestQuoteDoc,
    QuoteFields,
    Snapshot,
)
from acciones_ud.market_data.domain.quotes import from_snapshot, instant
from acciones_ud.shared.domain.alpaca_errors import AlpacaUnavailable
from acciones_ud.shared.infrastructure.alpaca_http import raise_for_alpaca


def _document(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise AlpacaUnavailable()
    return cast("dict[str, Any]", payload)


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _bar(document: dict[str, Any]) -> Bar:
    timestamp = instant(document.get("t"))
    if timestamp is None:
        raise AlpacaUnavailable()
    return Bar(
        timestamp=timestamp,
        open=_decimal(document["o"]),
        high=_decimal(document["h"]),
        low=_decimal(document["l"]),
        close=_decimal(document["c"]),
        volume=int(document.get("v") or 0),
    )


class AlpacaDataClient:
    def __init__(self, client: httpx.AsyncClient, feed: str) -> None:
        self.client = client
        self.feed = feed

    async def _get(self, path: str, params: dict[str, str]) -> httpx.Response:
        try:
            response = await self.client.get(path, params=params)
        except httpx.HTTPError:
            raise AlpacaUnavailable() from None
        raise_for_alpaca(response)
        return response

    async def snapshot(self, symbol: str) -> Snapshot:
        response = await self._get(f"/v2/stocks/{symbol}/snapshot", {"feed": self.feed})
        return from_snapshot(_document(response), self.feed)

    async def snapshots(self, symbols: list[str]) -> dict[str, Snapshot]:
        if not symbols:
            return {}
        response = await self._get(
            "/v2/stocks/snapshots", {"symbols": ",".join(symbols), "feed": self.feed}
        )
        payload = response.json()
        if not isinstance(payload, dict):
            raise AlpacaUnavailable()
        return {
            str(symbol): from_snapshot(document, self.feed)
            for symbol, document in payload.items()
            if isinstance(document, dict)
        }

    async def bars(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        page_size: int,
        page_token: str | None,
    ) -> BarsPage:
        params = {
            "timeframe": timeframe,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": str(page_size),
            "feed": self.feed,
            "sort": "asc",
        }
        if page_token is not None:
            params["page_token"] = page_token
        response = await self._get(f"/v2/stocks/{symbol}/bars", params)
        document = _document(response)
        raw_bars = document.get("bars")
        bars = [
            _bar(item)
            for item in (raw_bars if isinstance(raw_bars, list) else [])
            if isinstance(item, dict)
        ]
        token = document.get("next_page_token")
        return BarsPage(bars=bars, next_page_token=None if token is None else str(token))

    async def latest_quote(self, symbol: str) -> LatestQuoteDoc:
        response = await self._get(f"/v2/stocks/{symbol}/quotes/latest", {"feed": self.feed})
        document = _document(response)
        quote = document.get("quote")
        if not isinstance(quote, dict):
            return LatestQuoteDoc(quote=None)
        quote_doc = cast("dict[str, Any]", quote)
        return LatestQuoteDoc(
            quote=QuoteFields(
                bid_price=None if quote_doc.get("bp") is None else _decimal(quote_doc["bp"]),
                bid_size=None if quote_doc.get("bs") is None else int(quote_doc["bs"]),
                ask_price=None if quote_doc.get("ap") is None else _decimal(quote_doc["ap"]),
                ask_size=None if quote_doc.get("as") is None else int(quote_doc["as"]),
                timestamp=instant(quote_doc.get("t")),
            )
        )
