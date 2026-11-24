from collections.abc import AsyncIterator
from dataclasses import asdict
from datetime import datetime

from acciones_ud.admin.domain.model import LedgerExecution, Raw
from acciones_ud.orders.application.execution_ledger import ExecutionLedger, LedgerFilters


class PlatformLedger:
    def __init__(self, ledger: ExecutionLedger) -> None:
        self.ledger = ledger

    async def iterate(
        self, start: datetime, end: datetime, filters: Raw | None = None
    ) -> AsyncIterator[LedgerExecution]:
        selected = LedgerFilters(**filters) if filters else None
        async for execution in self.ledger.iterate_platform(start, end, filters=selected):
            yield LedgerExecution(**asdict(execution))

    async def volume(self, start: datetime, end: datetime) -> list[Raw]:
        return await self.ledger.volume(start, end)
