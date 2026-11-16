from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa

from acciones_ud.brokers.adapters.outbound.persistence.unit_of_work import build_work
from acciones_ud.brokers.domain.entities import BrokerProfile, Link, Rating
from acciones_ud.brokers.domain.entities import LinkStatus as S

pytestmark = pytest.mark.db


async def parties(session):
    owner = (await session.execute(sa.text("SELECT id FROM users LIMIT 1"))).scalar_one()
    broker = uuid4()
    await session.execute(
        sa.text("""INSERT INTO users
        (id,first_names,last_names,email,email_normalized,phone,password_hash,country,
         terms_accepted_at,monthly_report)
        VALUES (:id,'Broker','Test',:email,:email,'+573001234567',
        (SELECT password_hash FROM users LIMIT 1),'CO',now(),false)
    """),
        {"id": broker, "email": f"{broker}@example.test"},
    )
    return owner, broker


async def test_repository_roundtrip_conditional_updates_pages_and_rating_upsert(db_session):
    investor, broker = await parties(db_session)
    now = datetime.now(UTC)
    work = build_work(db_session)
    link = Link(uuid4(), investor, broker, S.REQUESTED, now, now + timedelta(days=7), "v1", now)
    await work.links.insert(link)
    assert await work.links.open_for(investor, for_update=True) == link
    active = replace(link, status=S.ACTIVE, started_at=now, responded_at=now)
    assert not await work.links.save(active, status=S.DECLINED)
    assert await work.links.save(active, status=S.REQUESTED)
    assert await work.links.page(
        investor, S.ACTIVE, now, now + timedelta(days=1), now, None, 20
    ) == ([active], None)
    profile = BrokerProfile(broker, "Stocks", 3, ("Finance",), "Profile", now)
    await work.profiles.upsert(profile)
    assert await work.profiles.get(broker_id=broker) == profile
    first = Rating(link.id, investor, broker, 2, "First", now, now)
    await work.ratings.upsert(first)
    latest = replace(first, stars=5, comment="Updated", updated_at=now + timedelta(seconds=1))
    assert await work.ratings.upsert(latest) == latest
    assert await work.ratings.page(broker, None, 20) == ([latest], None)
