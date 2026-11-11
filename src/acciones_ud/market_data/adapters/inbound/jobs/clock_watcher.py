"""RF-27: market clock watcher. Emits open/close events exactly on transitions."""

import asyncio
import logging

from acciones_ud.market_data.application.notifier import Notifier
from acciones_ud.market_data.domain.clock_watch import transitions
from acciones_ud.market_data.domain.ports import AlpacaBrokerMarketPort, DirectoryFactory
from acciones_ud.shared.domain.alpaca_errors import AlpacaError

logger = logging.getLogger(__name__)


class ClockWatcher:
    def __init__(
        self,
        broker: AlpacaBrokerMarketPort,
        directory: DirectoryFactory,
        notifier: Notifier,
        interval_seconds: int,
    ) -> None:
        self.broker = broker
        self.directory = directory
        self.notifier = notifier
        self.interval_seconds = interval_seconds
        self.previous: bool | None = None
        self._task: asyncio.Task[None] | None = None

    async def run_once(self) -> None:
        try:
            clock = await self.broker.clock()
        except AlpacaError:
            return
        current = clock.is_open
        events = transitions([self.previous, current])
        self.previous = current
        for event in events:
            async with self.directory() as directory:
                recipients = await directory.recipients(event)
            payload: dict[str, object] = {
                "event": event,
                "observed_at": clock.timestamp.isoformat(),
            }
            if event == "market_open":
                payload["next_open"] = clock.next_open.isoformat()
            else:
                payload["next_close"] = clock.next_close.isoformat()
            await self.notifier.notify(recipients, event, payload)

    async def run(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception:
                logger.exception("market clock check failed")
            await asyncio.sleep(self.interval_seconds)

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
