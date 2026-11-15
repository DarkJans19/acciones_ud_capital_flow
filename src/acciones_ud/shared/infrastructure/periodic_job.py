import asyncio
import contextlib
import logging
from typing import Protocol


class PeriodicWork(Protocol):
    async def run_once(self) -> None: ...


class PeriodicJob:
    def __init__(self, work: PeriodicWork, interval: float, name: str) -> None:
        self.work, self.interval, self.name = work, interval, name
        self.task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self.task is None:
            self.task = asyncio.create_task(self._run(), name=self.name)

    async def _run(self) -> None:
        while True:
            try:
                await self.work.run_once()
            except Exception:
                logging.getLogger(__name__).warning(
                    "Periodic work failed", extra={"job": self.name}
                )
            await asyncio.sleep(self.interval)

    async def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
            self.task = None
