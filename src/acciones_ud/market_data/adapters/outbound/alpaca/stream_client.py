"""RF-25: upstream Alpaca market data stream with reconnect and resubscription."""

import asyncio
import json
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import websockets

from acciones_ud.market_data.domain.entities import PriceUpdate

MAX_BACKOFF_SECONDS = 30


def parse_message(message: dict[str, Any]) -> PriceUpdate | None:
    kind = message.get("T")
    symbol = message.get("S")
    if not isinstance(symbol, str):
        return None
    if kind == "t" and message.get("p") is not None:
        return PriceUpdate(symbol=symbol.upper(), price=Decimal(str(message["p"])))
    if kind == "q":
        price = message.get("ap") if message.get("ap") is not None else message.get("bp")
        if price is None:
            return None
        return PriceUpdate(symbol=symbol.upper(), price=Decimal(str(price)))
    return None


class AlpacaStreamClient:
    def __init__(self, url: str, key: str, secret: str) -> None:
        self.url = url
        self.key = key
        self.secret = secret
        self._socket: Any | None = None
        self._symbols: set[str] = set()
        self._lock = asyncio.Lock()

    async def _connect(self) -> None:
        socket = await websockets.connect(self.url)
        await socket.send(
            json.dumps({"action": "auth", "key": self.key, "secret": self.secret})
        )
        await socket.recv()
        self._socket = socket
        if self._symbols:
            await socket.send(self._subscription(self._symbols))

    def _subscription(self, symbols: set[str]) -> str:
        return json.dumps({"action": "subscribe", "trades": sorted(symbols)})

    async def subscribe(self, symbols: set[str]) -> None:
        async with self._lock:
            if symbols == self._symbols:
                return
            self._symbols = set(symbols)
            if self._socket is not None and symbols:
                await self._socket.send(self._subscription(self._symbols))

    async def close(self) -> None:
        if self._socket is not None:
            await self._socket.close()
            self._socket = None

    async def stream(self) -> AsyncIterator[PriceUpdate]:
        backoff = 1
        while True:
            try:
                if self._socket is None:
                    await self._connect()
                assert self._socket is not None
                async for raw in self._socket:
                    payload = json.loads(raw)
                    messages = payload if isinstance(payload, list) else [payload]
                    for message in messages:
                        if isinstance(message, dict):
                            update = parse_message(message)
                            if update is not None:
                                yield update
                await self.close()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._socket = None
                await asyncio.sleep(backoff)
                backoff = min(MAX_BACKOFF_SECONDS, backoff * 2)
