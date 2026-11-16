from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa

from acciones_ud.brokers.adapters.outbound.broker_link_adapter import BrokerLinkAdapter
from acciones_ud.brokers.adapters.outbound.identity.associated_broker_reader import (
    AssociatedBrokerReader,
)
from acciones_ud.brokers.adapters.outbound.persistence.unit_of_work import build_work
from acciones_ud.brokers.domain.entities import Link
from acciones_ud.brokers.domain.entities import LinkStatus as S
from tests.brokers.unit.test_repository_db import parties

pytestmark = pytest.mark.db


async def test_sql_membership_changes_immediately_with_link_and_role(db_session):
    investor, broker = await parties(db_session)
    now = datetime.now(UTC)

    @asynccontextmanager
    async def sessions():
        yield db_session

    work, adapter = build_work(db_session), BrokerLinkAdapter(sessions)
    link = Link(
        uuid4(),
        investor,
        broker,
        S.ACTIVE,
        now,
        now + timedelta(days=7),
        "v1",
        now,
        started_at=now,
        order_review_enabled=True,
    )
    await work.links.insert(link)
    assert not await adapter.is_linked(broker, investor)
    await db_session.execute(
        sa.text("""INSERT INTO role_assignments
        (id,user_id,role_code,valid_from) VALUES (:id,:broker,'broker',:start)
    """),
        {"id": uuid4(), "broker": broker, "start": now - timedelta(days=1)},
    )
    assert await adapter.is_linked(broker, investor)
    assert await adapter.linked_investors(broker) == [investor]
    assert await adapter.reviewing_broker(investor) == broker
    reader = AssociatedBrokerReader(sessions)
    associated = await reader.associated_broker(investor)
    assert associated.id == broker and associated.name == "Broker Test" and associated.since == now
    await work.links.save(replace(link, status=S.ENDED, ended_at=now))
    assert not await adapter.is_linked(broker, investor)
    assert await adapter.linked_investors(broker) == []
    assert await adapter.reviewing_broker(investor) is None
    assert await reader.associated_broker(investor) is None
    await work.links.save(link)
    await db_session.execute(
        sa.text("""UPDATE role_assignments
        SET valid_to=:now WHERE user_id=:broker"""),
        {"now": now, "broker": broker},
    )
    assert not await adapter.is_linked(broker, investor)
