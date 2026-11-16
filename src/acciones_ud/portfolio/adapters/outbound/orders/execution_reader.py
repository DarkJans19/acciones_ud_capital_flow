from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from acciones_ud.orders.application.execution_ledger import ExecutionLedger
from acciones_ud.portfolio.domain.model import ExecutionRecord, Page


class ExecutionReader:
    def __init__(self, ledger: ExecutionLedger) -> None:
        self.ledger = ledger

    async def list(
        self,
        user_id: UUID,
        until: datetime | None = None,
        since: datetime | None = None,
        symbol: str | None = None,
    ) -> list[ExecutionRecord]:
        return [
            ExecutionRecord(**asdict(e))
            for e in await self.ledger.list(user_id, until, since, symbol)
        ]

    async def list_page(
        self,
        user_id: UUID,
        since: datetime,
        until: datetime,
        symbol: str | None,
        cursor: str | None,
        size: int,
    ) -> Page[ExecutionRecord]:
        items, next_cursor = await self.ledger.list_page(
            user_id, since, until, symbol, cursor, size
        )
        return Page([ExecutionRecord(**asdict(e)) for e in items], next_cursor)
