from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa

from acciones_ud.brokers.adapters.outbound.identity.broker_directory import BrokerDirectory
from acciones_ud.brokers.adapters.outbound.identity.broker_request_reader import BrokerRequestReader
from acciones_ud.brokers.adapters.outbound.identity.linked_account_reader import LinkedAccountReader
from tests.brokers.unit.test_repository_db import parties

pytestmark = pytest.mark.db


async def test_directory_observes_role_validity_and_private_readers(db_session):
    investor, broker = await parties(db_session)

    @asynccontextmanager
    async def session():
        yield db_session

    directory = BrokerDirectory(session)
    assert await directory.get_broker(broker) is None
    await db_session.execute(
        sa.text("""INSERT INTO role_assignments
        (id,user_id,role_code,valid_from) VALUES (:id,:user_id,'broker',:start)
    """),
        {"id": uuid4(), "user_id": broker, "start": datetime.now(UTC) - timedelta(days=1)},
    )
    identity = await directory.get_broker(broker)
    assert identity.name == "Broker Test"
    assert await directory.has_role(broker, "broker")
    assert await directory.search("bro", investor, None, 20) == [identity]
    assert await directory.search("%", investor, None, 20) == []
    assert await directory.all_active(broker) == []
    assert not await BrokerRequestReader(session).broker_requested(investor)
    assert not await LinkedAccountReader(session).has_linked_account(investor)
    await db_session.execute(
        sa.text("""UPDATE role_assignments
        SET status='CANCELLED',cancelled_at=now(),cancelled_by=:broker WHERE user_id=:broker
    """),
        {"broker": broker},
    )
    assert await directory.get_broker(broker) is None
    assert not await directory.has_role(broker, "broker")
