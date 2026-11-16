from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from acciones_ud.brokers.adapters.outbound.broker_link_adapter import BrokerLinkAdapter


async def test_each_membership_operation_uses_one_uncached_query():
    investor, broker = uuid4(), uuid4()
    result = MagicMock()
    result.first.return_value = (investor,)
    result.__iter__.return_value = iter([(investor, None)])
    result.scalar_one_or_none.return_value = broker
    session = MagicMock(execute=AsyncMock(return_value=result))

    @asynccontextmanager
    async def sessions():
        yield session

    adapter = BrokerLinkAdapter(sessions)
    assert await adapter.is_linked(broker, investor)
    assert await adapter.linked_investors(broker) == [investor]
    assert await adapter.reviewing_broker(investor) == broker
    assert session.execute.await_count == 3
    for call in session.execute.await_args_list:
        query = str(call.args[0])
        assert "JOIN role_assignments" in query and "valid_from" in query and "valid_to" in query
