from datetime import UTC, datetime
from uuid import uuid4

from acciones_ud.orders.domain.model import Execution
from tests.orders.fakes import MemoryFactory


async def test_execution_deduplication_and_transaction_rollback() -> None:
    uow = MemoryFactory()
    fill = Execution("execution", uuid4(), 1, 10, datetime.now(UTC), datetime.now(UTC))
    async with uow() as work:
        assert await work.executions.insert(fill)
        assert not await work.executions.insert(fill)
    try:
        async with uow() as work:
            await work.executions.delete(alpaca_execution_id="execution")
            raise ValueError()
    except ValueError:
        pass
    assert await uow.work.executions.get(alpaca_execution_id="execution") == fill
