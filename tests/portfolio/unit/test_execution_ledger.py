from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from sqlalchemy.dialects.postgresql import dialect

from acciones_ud.orders.adapters.outbound.persistence.execution_repository import (
    ExecutionRepository,
    query,
)


def test_ledger_query_uses_last_broker_signature_and_exclusive_end():
    sql = str(
        query(uuid4(), datetime.now(UTC), datetime.now(UTC), "AAPL").compile(
            dialect=dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "LEFT OUTER JOIN LATERAL" in sql
    assert "order_events.actor_type = 'broker'" in sql
    assert "order_events.to_status = 'BROKER_SIGNED'" in sql
    assert "ORDER BY order_events.at DESC, order_events.id DESC" in sql
    assert "order_executions.executed_at <" in sql
    assert "orders.user_id =" in sql


async def test_keyset_cursor_with_text_execution_id():
    now, owner = datetime.now(UTC), uuid4()
    rows = [
        dict(
            execution_id=i,
            order_id=uuid4(),
            user_id=owner,
            symbol="AAPL",
            exchange="NYSE",
            side="buy",
            qty=1,
            price=2,
            executed_at=now,
            signed_by_broker_id=None,
        )
        for i in ["fill-b", "fill-a"]
    ]
    result = Mock()
    result.mappings.return_value = rows
    session = Mock(execute=AsyncMock(return_value=result))
    repo = ExecutionRepository(session)
    page, cursor = await repo.list_page(owner, now, now, None, None, 1)
    assert page[0].execution_id == "fill-b" and cursor
    await repo.list_page(owner, now, now, None, cursor, 1)
    statement = session.execute.call_args[0][0]
    sql = str(statement.compile(dialect=dialect(), compile_kwargs={"literal_binds": True}))
    assert "fill-b" in sql
