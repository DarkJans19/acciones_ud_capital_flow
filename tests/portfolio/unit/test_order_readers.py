from dataclasses import asdict
from decimal import Decimal
from unittest.mock import AsyncMock

from acciones_ud.orders.application.execution_ledger import LedgerExecution
from acciones_ud.portfolio.adapters.outbound.orders.execution_reader import ExecutionReader
from acciones_ud.portfolio.adapters.outbound.orders.reservation_reader import ReservationReader
from tests.portfolio.property.test_pnl import records


async def test_reads_preserve_order_contracts():
    row = records([("buy", Decimal(1), Decimal(2))])[0]
    ledger = AsyncMock()
    ledger.list.return_value = [LedgerExecution(**asdict(row))]
    ledger.list_page.return_value = ([LedgerExecution(**asdict(row))], "next")
    ledger.active_share_reservations.return_value = {"A": Decimal(2)}
    reader = ExecutionReader(ledger)
    assert await reader.list(row.user_id) == [row]
    assert (
        await reader.list_page(row.user_id, row.executed_at, row.executed_at, None, None, 50)
    ).next_cursor == "next"
    assert await ReservationReader(ledger).active_share_reservations(row.user_id) == {
        "A": Decimal(2)
    }
