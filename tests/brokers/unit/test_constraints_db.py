from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError, IntegrityError

from acciones_ud.brokers.adapters.outbound.persistence import models as t
from acciones_ud.brokers.adapters.outbound.persistence.unit_of_work import build_work
from acciones_ud.brokers.domain.entities import (
    BrokerEvent,
    Link,
    LinkStatus,
    Proposal,
    ProposalDecision,
    ProposalMessage,
    ProposalStatus,
    ProposalVersion,
    TradingAuthorization,
)
from acciones_ud.brokers.domain.errors import LinkAlreadyExistsError
from tests.brokers.unit.test_repository_db import parties

pytestmark = pytest.mark.db


async def test_partial_uniqueness_approved_check_and_immutable_evidence(db_session):
    investor, broker = await parties(db_session)
    now = datetime.now(UTC)
    work = build_work(db_session)
    link = Link(
        uuid4(), investor, broker, LinkStatus.ACTIVE, now, now + timedelta(days=7), "v1", now
    )
    await work.links.insert(link)
    with pytest.raises(LinkAlreadyExistsError):
        async with db_session.begin_nested():
            await work.links.insert(replace(link, id=uuid4()))
    authorization = TradingAuthorization(uuid4(), link.id, "v1", now)
    await work.authorizations.insert(authorization)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await work.authorizations.insert(replace(authorization, id=uuid4()))
    proposal = Proposal(
        uuid4(),
        link.id,
        broker,
        investor,
        ProposalStatus.SENT,
        1,
        now,
        now,
        now,
        now + timedelta(hours=72),
    )
    await work.proposals.insert(proposal)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await work.proposals.save(replace(proposal, status=ProposalStatus.APPROVED))
    version = ProposalVersion(
        proposal.id,
        1,
        "AAPL",
        "buy",
        Decimal(1),
        "market",
        None,
        Decimal(100),
        Decimal(102),
        now,
    )
    await work.versions.insert(version)
    message = ProposalMessage(uuid4(), proposal.id, investor, "Evidence", now)
    await work.messages.insert(message)
    decision = ProposalDecision(uuid4(), proposal.id, 1, investor, "investor", "accept", now)
    await work.decisions.insert(decision)
    event = BrokerEvent(uuid4(), "proposal", proposal.id, None, "sent", "broker", broker, None, now)
    await work.events.insert(event)
    for table in (t.versions, t.messages, t.decisions, t.events):
        for operation in (
            sa.update(table).values(**{next(iter(table.c)).name: next(iter(table.c))}),
            sa.delete(table),
        ):
            with pytest.raises(DBAPIError, match="Immutable broker evidence"):
                async with db_session.begin_nested():
                    await db_session.execute(operation)
    assert await work.versions.get(proposal_id=proposal.id, version=1) == version
    assert await work.messages.page(proposal.id, None, 20) == ([message], None)
    flags = (
        await db_session.execute(
            sa.text("""SELECT count(*) FROM pg_class
        WHERE relname LIKE 'broker_%' AND relkind = 'r' AND relrowsecurity""")
        )
    ).scalar_one()
    assert flags == 9
