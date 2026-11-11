"""Alpaca Broker API: assets, calendar and clock (RF-24, RF-27)."""

from datetime import date, datetime, time
from typing import Any, cast
from uuid import UUID

import httpx

from acciones_ud.market_data.domain.entities import (
    CalendarSession,
    Instrument,
    MarketClock,
)
from acciones_ud.shared.domain.alpaca_errors import AlpacaUnavailable
from acciones_ud.shared.infrastructure.alpaca_http import raise_for_alpaca


def _uuid_or_none(value: object) -> UUID | None:
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


def _document(response: httpx.Response) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise AlpacaUnavailable()
    return cast("dict[str, Any]", payload)


def _documents(response: httpx.Response) -> list[dict[str, Any]]:
    payload = response.json()
    if not isinstance(payload, list):
        raise AlpacaUnavailable()
    return [cast("dict[str, Any]", item) for item in payload if isinstance(item, dict)]


def _instant(value: object) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def to_instrument(document: dict[str, Any]) -> Instrument:
    return Instrument(
        symbol=str(document["symbol"]).upper(),
        name=str(document.get("name") or ""),
        exchange=str(document.get("exchange") or ""),
        asset_class=str(document.get("class") or "us_equity"),
        status=str(document.get("status") or "active"),
        tradable=bool(document.get("tradable")),
        marginable=bool(document.get("marginable")),
        shortable=bool(document.get("shortable")),
        easy_to_borrow=bool(document.get("easy_to_borrow")),
        fractionable=bool(document.get("fractionable")),
        alpaca_asset_id=_uuid_or_none(document.get("id")),
    )


class AlpacaBrokerMarketClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def _get(self, path: str, params: dict[str, str] | None = None) -> httpx.Response:
        try:
            response = await self.client.get(path, params=params)
        except httpx.HTTPError:
            raise AlpacaUnavailable() from None
        raise_for_alpaca(response)
        return response

    async def list_assets(self) -> list[Instrument]:
        response = await self._get("/v1/assets", {"asset_class": "us_equity", "status": "active"})
        return [to_instrument(document) for document in _documents(response)]

    async def get_asset(self, symbol: str) -> Instrument:
        response = await self._get(f"/v1/assets/{symbol}")
        return to_instrument(_document(response))

    async def calendar(self, start: date, end: date) -> list[CalendarSession]:
        response = await self._get(
            "/v1/calendar", {"start": start.isoformat(), "end": end.isoformat()}
        )
        sessions: list[CalendarSession] = []
        for document in _documents(response):
            try:
                sessions.append(
                    CalendarSession(
                        date=date.fromisoformat(str(document["date"])),
                        open_at=time.fromisoformat(str(document["open"])),
                        close_at=time.fromisoformat(str(document["close"])),
                    )
                )
            except (KeyError, ValueError):
                raise AlpacaUnavailable() from None
        return sessions

    async def clock(self) -> MarketClock:
        response = await self._get("/v1/clock")
        document = _document(response)
        try:
            return MarketClock(
                is_open=bool(document["is_open"]),
                next_open=_instant(document["next_open"]),
                next_close=_instant(document["next_close"]),
                timestamp=_instant(document["timestamp"]),
            )
        except (KeyError, TypeError, ValueError):
            raise AlpacaUnavailable() from None
