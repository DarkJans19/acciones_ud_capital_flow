from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from acciones_ud.orders.adapters.outbound.persistence.order_repository import OrderRepository
from acciones_ud.orders.adapters.outbound.persistence.unit_of_work import build_work


async def test_scheduler_uses_skip_locked_and_owner_lock_is_transactional() -> None:
    session = AsyncMock()
    result = Mock()
    result.mappings.return_value = []
    session.execute.return_value = result
    work = build_work(session)
    await work.lock_user(uuid4())
    assert "pg_advisory_xact_lock" in str(session.execute.call_args.args[0])
    await OrderRepository(session).due(datetime.now(UTC))
    sql = str(session.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE SKIP LOCKED" in sql
    assert "orders.returned_for_changes IS false" in sql
