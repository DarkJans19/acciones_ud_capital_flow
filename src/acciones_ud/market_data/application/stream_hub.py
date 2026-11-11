"""RF-25: fan out upstream price updates to subscribed WebSocket clients."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from acciones_ud.market_data.domain.ports import StreamUpstreamPort
from acciones_ud.market_data.domain.streaming import SubscriptionRegistry

logger = logging.getLogger(__name__)


class StreamHub:
    def __init__(
        self,
        registry: SubscriptionRegistry,
        upstream: StreamUpstreamPort,
        catalog_symbols: Callable[[], Awaitable[set[str]]],
    ) -> None:
        self.registry = registry
        self.upstream = upstream
        self.catalog_symbols = catalog_symbols
        self.sockets: dict[str, object] = {}
        self._task: asyncio.Task[None] | None = None

    async def register(self, client_id: str, socket: object) -> None:
        self.sockets[client_id] = socket

    async def unregister(self, client_id: str) -> None:
        self.sockets.pop(client_id, None)
        self.registry.disconnect(client_id)
        await self.upstream.subscribe(self.registry.upstream())

    async def subscribe(self, client_id: str, symbols: list[str]) -> bool:
        catalog = await self.catalog_symbols()
        accepted = self.registry.subscribe(client_id, symbols, catalog)
        if accepted:
            await self.upstream.subscribe(self.registry.upstream())
        return accepted

    async def run(self) -> None:
        async for update in self.upstream.stream():
            payload = {
                "type": "price",
                "symbol": update.symbol,
                "price": None if update.price is None else str(update.price),
                "timestamp": None
                if update.timestamp is None
                else update.timestamp.isoformat(),
            }
            for client_id in self.registry.targets(update.symbol):
                socket = self.sockets.get(client_id)
                if socket is None:
                    continue
                try:
                    await socket.send_json(payload)  # type: ignore[attr-defined]
                except Exception:
                    logger.warning("dropping stream client %s", client_id)
                    await self.unregister(client_id)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self.upstream.close()
        for socket in list(self.sockets.values()):
            try:
                await socket.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        self.sockets.clear()
