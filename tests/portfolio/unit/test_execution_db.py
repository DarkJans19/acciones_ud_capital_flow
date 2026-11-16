from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa

from acciones_ud.orders.adapters.outbound.persistence.execution_repository import (
    ExecutionRepository,
)
from acciones_ud.orders.adapters.outbound.persistence.unit_of_work import build_work
from acciones_ud.orders.domain.model import Execution, OrderEvent, Reservation
from tests.orders.support import make_order


@pytest.mark.db
async def test_broker_signature_and_ledger_page(db_session):
    owner = (await db_session.execute(sa.text("SELECT id FROM users LIMIT 1"))).scalar_one()
    work = build_work(db_session)
    now, broker = datetime.now(UTC), uuid4()
    order = make_order(owner)
    await work.orders.insert(order)
    for i, actor in enumerate(["broker", "investor"]):
        await work.events.insert(
            OrderEvent(
                uuid4(),
                order.id,
                "PENDING",
                "BROKER_SIGNED",
                "approved",
                actor,
                broker,
                now + timedelta(seconds=i),
            )
        )
    for ident in ["b", "a"]:
        await work.executions.insert(Execution(ident, order.id, Decimal(1), Decimal(10), now, now))
    await work.reservations.insert(
        Reservation(order.id, owner, "shares", "AAPL", Decimal(2), "active", now)
    )
    repo = ExecutionRepository(db_session)
    first, cursor = await repo.list_page(owner, now, now + timedelta(days=1), None, None, 1)
    assert first[0].signed_by_broker_id == broker
    assert first[0].execution_id == "b" and cursor
    second, end = await repo.list_page(owner, now, now + timedelta(days=1), None, cursor, 1)
    assert second[0].execution_id == "a" and end is None
    assert await repo.active_share_reservations(owner) == {"AAPL": Decimal(2)}
